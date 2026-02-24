"""
Agent Routes
Endpoints for endpoint agent events with node validation
"""

from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import json
import zipfile
import io
import socket
from pathlib import Path
import asyncio
import httpx

from backend.models.log_models import AgentEvent, Alert, NetworkEvent, BlockedIP
from backend.services.db_service import db_service
from backend.services.ml_service import ml_service
from backend.services.node_service import node_service
from backend.services.node_auth import validate_node_access
from backend.services.notification_service import notification_service
from backend.config import ALERT_RISK_THRESHOLD, AUTH_ENABLED, DEMO_USER_ID, ABUSEIPDB_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agent"])

_PRIVATE_PREFIXES = ('10.', '172.16.', '172.17.', '172.18.', '172.19.',
                     '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
                     '172.25.', '172.26.', '172.27.', '172.28.', '172.29.',
                     '172.30.', '172.31.', '192.168.', '127.', '::1', 'localhost')


async def _enrich_ip(ip: str) -> Dict[str, Any]:
    """
    Enrich an IP with geolocation, reverse DNS, and optional AbuseIPDB reputation.
    All lookups are best-effort — failures return an empty dict, never raise.
    Free-tier sources: ip-api.com (geo) + socket (rDNS) + AbuseIPDB (if key set).
    """
    if not ip or any(ip.startswith(p) for p in _PRIVATE_PREFIXES):
        return {"type": "private/local"}

    enriched: Dict[str, Any] = {}

    # 1. Reverse DNS (stdlib — no external dependency)
    try:
        rdns = await asyncio.get_event_loop().run_in_executor(
            None, lambda: socket.gethostbyaddr(ip)[0]
        )
        enriched["rdns"] = rdns
    except Exception:
        pass

    # 2. Geolocation — ip-api.com (free, no key, 45 req/min)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,regionName,city,isp,org,as,lat,lon"}
            )
            data = resp.json()
            if data.get("status") == "success":
                enriched["geo"] = {
                    "country":      data.get("country"),
                    "country_code": data.get("countryCode"),
                    "region":       data.get("regionName"),
                    "city":         data.get("city"),
                    "isp":          data.get("isp"),
                    "org":          data.get("org"),
                    "asn":          data.get("as"),
                    "lat":          data.get("lat"),
                    "lon":          data.get("lon"),
                }
    except Exception:
        pass

    # 3. AbuseIPDB reputation (only if API key is configured)
    if ABUSEIPDB_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    headers={"Key": ABUSEIPDB_API_KEY, "Accept": "application/json"},
                    params={"ipAddress": ip, "maxAgeInDays": 90}
                )
                d = resp.json().get("data", {})
                enriched["abuse"] = {
                    "confidence_score": d.get("abuseConfidenceScore", 0),
                    "total_reports":    d.get("totalReports", 0),
                    "last_reported":    d.get("lastReportedAt"),
                    "is_tor":           d.get("isTor", False),
                    "country_code":     d.get("countryCode"),
                }
        except Exception:
            pass

    return enriched


@router.post("/agent-alert")
async def receive_agent_event(
    request: Request,
    event: AgentEvent,
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Receive honeytoken trigger event from endpoint agents
    
    Headers:
    - X-Node-Id: Node ID for authentication (required if AUTH_ENABLED)
    - X-Node-Key: Node API key for authentication (required if AUTH_ENABLED)
    
    Flow:
    1. Validate X-Node-Id and X-Node-Key (if AUTH_ENABLED)
    2. Update node.last_seen
    3. Save decoy access record
    4. Call ML API for prediction
    5. Save event + prediction to MongoDB
    6. If risk_score > 7, create alert with node_id and user_id
    7. Update attacker profile
    8. Return response
    """
    try:
        logger.info(f"📥 Agent event received: {event.alert_type} from {event.hostname}")
        
        # Step 1: Validate node_id, API key, and get user_id
        user_id = DEMO_USER_ID
        node_id = x_node_id
        
        if AUTH_ENABLED:
            node = await validate_node_access(x_node_id, x_node_key)
            
            user_id = node["user_id"]
            node_id = node["node_id"]
            
            # Update node last_seen
            await db_service.update_node_last_seen(
                node_id,
                node_service.update_last_seen(node_id)
            )
        
        # Step 2: Save decoy access record
        if node_id:
            decoy_data = {
                "node_id": node_id,
                "file_name": event.file_accessed,
                "type": "honeytoken",
                "last_accessed": event.timestamp
            }
            await db_service.save_decoy_access(decoy_data)
        
        # Step 3: Get ML prediction
        event_data = event.dict()
        event_data["node_id"] = node_id
        ml_prediction = await ml_service.predict_attack(event_data)
        
        if ml_prediction:
            logger.info(f"🧠 ML Prediction: {ml_prediction.attack_type} (Risk: {ml_prediction.risk_score}/10)")
        else:
            logger.warning("⚠️ ML prediction failed, saving event without prediction")
        
        # Step 4: Save event to database
        event_id = await db_service.save_agent_event(
            event_data,
            ml_prediction.dict() if ml_prediction else None
        )
        
        # Step 5: Build enrichment metadata
        client_ip = request.client.host if request.client else None
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        extra: Dict[str, Any] = {}
        # Process context (from file_monitor psutil capture)
        for field in ("process_name", "pid", "process_user", "cmdline"):
            val = getattr(event, field, None)
            if val is not None:
                extra[field] = val
        # Geolocation of the agent's endpoint (shows where the monitored machine is)
        if client_ip:
            extra["endpoint"] = await _enrich_ip(client_ip)

        # Step 6: Create alert if high risk
        alert_created = False
        if ml_prediction and ml_prediction.risk_score >= ALERT_RISK_THRESHOLD:
            alert = Alert(
                alert_id=f"AGENT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{event.hostname[:8]}",
                timestamp=event.timestamp,
                source_ip=event.hostname,  # Use hostname as identifier
                service="endpoint_agent",
                attack_type=ml_prediction.attack_type,
                risk_score=ml_prediction.risk_score,
                confidence=ml_prediction.confidence,
                activity=event.action,
                payload=event.file_accessed,
                node_id=node_id,
                user_id=user_id,
                extra=extra or None,
            )
            await db_service.create_alert(alert)
            alert_created = True

            # Fire notifications asynchronously across all channels (Slack/Email/WhatsApp)
            asyncio.create_task(notification_service.broadcast_alert(alert))
        
        # Step 7: Update attacker profile (use hostname as IP)
        if ml_prediction:
            await db_service.update_attacker_profile(
                source_ip=event.hostname,
                attack_type=ml_prediction.attack_type,
                risk_score=ml_prediction.risk_score,
                service="endpoint_agent"
            )
        
        return {
            "status": "success",
            "event_id": event_id,
            "ml_prediction": ml_prediction.dict() if ml_prediction else None,
            "alert_created": alert_created
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing agent event: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/register")
async def register_agent(
    node_id: str,
    hostname: str,
    os: str,
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Register agent with backend (first-time agent startup)
    
    Headers:
    - X-Node-Id: Node ID from config
    - X-Node-Key: Node API key from config
    
    Flow:
    1. Validate node_id and API key from headers
    2. Update node status to "online"
    3. Record registration timestamp
    4. Return registration confirmation
    """
    try:
        logger.info(f"📝 Agent registration: {node_id} ({hostname})")
        
        if AUTH_ENABLED:
            # Validate node_id and API key
            try:
                node = await validate_node_access(x_node_id, x_node_key)
                node_id = node["node_id"]
            except HTTPException:
                raise HTTPException(status_code=401, detail="Invalid node credentials")
        
        # Update node status
        await db_service.update_node_status(node_id, "online")
        
        # Record agent properties
        await db_service.update_node(node_id, {
            "last_seen": datetime.utcnow().isoformat(),
            "agent_status": "registered",
            "hostname": hostname,
            "os": os
        })
        
        logger.info(f"✓ Agent registered: {node_id}")
        
        return {
            "status": "success",
            "node_id": node_id,
            "message": f"Agent registered successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/heartbeat")
async def agent_heartbeat(
    request: Request,
    x_node_api_key: Optional[str] = Header(None, alias="X-Node-API-Key"),
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Agent heartbeat (keep-alive ping)
    
    Headers:
    - X-Node-API-Key: Node API key from config (preferred)
    - X-Node-Id: Node ID from config (deprecated)
    - X-Node-Key: Node API key from config (deprecated)
    
    Updates node last_seen and status to 'active'
    Also captures the client IP address on first connect
    """
    try:
        node_id = None
        
        # Get client IP address
        client_ip = request.client.host if request.client else None
        # Check for X-Forwarded-For (when behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        # Try X-Node-API-Key first (new format)
        if x_node_api_key:
            node = await db_service.get_node_by_api_key(x_node_api_key)
            if node:
                node_id = node["node_id"]
            else:
                raise HTTPException(status_code=401, detail="Invalid API key")
        elif AUTH_ENABLED:
            try:
                node = await validate_node_access(x_node_id, x_node_key)
                node_id = node["node_id"]
            except HTTPException:
                raise HTTPException(status_code=401, detail="Invalid node credentials")
        else:
            raise HTTPException(status_code=401, detail="No credentials provided")
        
        # Fetch node for uninstall status
        node = await db_service.get_node_by_id(node_id)
        uninstall_requested = bool(node and node.get("uninstall_requested"))

        # Update node status and update last_seen + IP address
        if uninstall_requested:
            await db_service.update_node_status(node_id, "uninstall_requested")
        else:
            await db_service.update_node_status(node_id, "active")

        update_data = {
            "last_seen": datetime.utcnow().isoformat(),
            "ip_address": client_ip
        }
        
        # If node was in installer_ready state, mark as fully active now
        if node and node.get("status") == "installer_ready":
            update_data["agent_status"] = "active"
            logger.info(f"🎉 Node {node_id} activated from installer_ready state")
        
        await db_service.update_node(node_id, update_data)
        
        logger.info(f"💓 Heartbeat from node: {node_id} (IP: {client_ip})")

        # Return any pending IP blocks so the agent can apply firewall rules
        pending_blocks = await db_service.get_pending_blocks(node_id)

        # Return current deployment config so the agent can deploy newly-requested decoys
        deployment_config = node.get("deployment_config", {}) if node else {}

        return {
            "status": "success",
            "message": "Heartbeat received",
            "node_id": node_id,
            "uninstall": uninstall_requested,
            "pending_blocks": pending_blocks,
            "deployment_config": deployment_config,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/uninstall-complete")
async def agent_uninstall_complete(
    x_node_api_key: Optional[str] = Header(None, alias="X-Node-API-Key"),
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Agent reports uninstall complete.

    Deletes node and related decoys from database.
    """
    try:
        node_id = None

        if x_node_api_key:
            node = await db_service.get_node_by_api_key(x_node_api_key)
            if node:
                node_id = node["node_id"]
            else:
                raise HTTPException(status_code=401, detail="Invalid API key")
        elif AUTH_ENABLED:
            try:
                node = await validate_node_access(x_node_id, x_node_key)
                node_id = node["node_id"]
            except HTTPException:
                raise HTTPException(status_code=401, detail="Invalid node credentials")
        else:
            raise HTTPException(status_code=401, detail="No credentials provided")

        await db_service.delete_node_and_decoys(node_id)

        return {
            "status": "success",
            "message": f"Node {node_id} deleted after uninstall"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing uninstall complete: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/download/{node_id}")
async def download_agent(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Download agent configuration and executable
    
    Generates config.json with node_id and node_api_key
    Returns ZIP with agent executable + config
    
    Flow:
    1. Verify node exists
    2. Generate config.json with credentials
    3. Create ZIP with executable + config
    4. Return as file download
    """
    try:
        # Verify node exists
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        logger.info(f"📥 Agent download requested: {node_id}")
        
        # Generate config.json
        config = {
            "node_id": node.get("node_id"),
            "node_api_key": node.get("node_api_key"),
            "backend_url": "https://ml-modle-v0-1.onrender.com/api",
            "express_backend_url": "https://decoyverse-v2.onrender.com/api",
            "version": "2.0.0",
            "deployment_config": node.get("deployment_config", {
                "initial_decoys": 3,
                "initial_honeytokens": 5,
                "deploy_path": None
            }),
            "endpoints": {
                "agent_alert": "/api/agent-alert",
                "register": "/api/agent/register",
                "heartbeat": "/api/agent/heartbeat"
            }
        }
        
        # Create in-memory ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add config.json
            config_json = json.dumps(config, indent=2)
            zip_file.writestr("config.json", config_json)
            
            # Add placeholder agent stub (in production would be real executable)
            agent_stub = f"""#!/usr/bin/env python3
# DecoyVerse Agent v2.0.0
# Node: {node_id}
# Auto-generated configuration

import json
import requests
import platform
import socket
from datetime import datetime

CONFIG = {json.dumps(config, indent=4)}

def register():
    '''Register agent with backend'''
    try:
        response = requests.post(
            f"{{CONFIG['backend_url']}}{{CONFIG['endpoints']['register']}}",
            headers={{
                "X-Node-Id": CONFIG["node_id"],
                "X-Node-Key": CONFIG["node_api_key"]
            }},
            json={{
                "node_id": CONFIG["node_id"],
                "hostname": socket.gethostname(),
                "os": platform.system()
            }},
            timeout=10
        )
        print(f"Registration response: {{response.status_code}}")
        return response.json()
    except Exception as e:
        print(f"Registration failed: {{e}}")
        return None

if __name__ == "__main__":
    print(f"DecoyVerse Agent v2.0.0")
    print(f"Node ID: {{CONFIG['node_id']}}")
    print(f"Starting registration...")
    result = register()
    if result:
        print(f"✓ Agent registered successfully")
    else:
        print(f"✗ Agent registration failed")
"""
            zip_file.writestr("agent.py", agent_stub)
            
            # Add setup/installation script
            setup_script = f"""#!/bin/bash
# DecoyVerse Agent Setup Script
# Installation and configuration for node: {node_id}

echo "DecoyVerse Agent Installation"
echo "Node ID: {node_id}"
echo "================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

# Install requirements
pip3 install requests

# Make agent executable
chmod +x agent.py

# Run agent
echo "Starting agent..."
python3 agent.py

# For systemd service (optional)
# sudo cp agent.service /etc/systemd/system/
# sudo systemctl daemon-reload
# sudo systemctl enable decoyverse-agent
# sudo systemctl start decoyverse-agent
"""
            zip_file.writestr("setup.sh", setup_script)
            
            # Add README
            readme = f"""# DecoyVerse Agent v2.0.0

Node Configuration:
- Node ID: {node.get("node_id")}
- API Key: {node.get("node_api_key")}
- Status: {node.get("status")}
- Created: {node.get("created_at")}

## Installation

### Linux/macOS
```bash
bash setup.sh
```

### Windows
```cmd
python agent.py
```

## Configuration

The agent will automatically use the config.json file for:
- Node authentication
- Backend connection
- Event reporting

## Features

- Honeytoken monitoring
- File integrity monitoring
- Network activity logging
- Automatic threat reporting
- Keep-alive heartbeat

## Troubleshooting

Check logs:
```bash
cat agent.log
```

Verify connectivity:
```bash
curl -I https://api.decoyverse.example.com/health
```
"""
            zip_file.writestr("README.md", readme)
        
        # Return ZIP file
        zip_buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=decoyverse-agent-{node_id}.zip"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/register-decoys")
async def register_deployed_decoys(
    request: Request,
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Register deployed decoys from agent after initial deployment
    
    Headers:
    - X-Node-Id: Node ID for authentication
    - X-Node-Key: Node API key for authentication
    
    Body:
    - List of deployed decoys with file_name, file_path, type
    """
    try:
        # Parse JSON body as list
        decoys = await request.json()
        if not isinstance(decoys, list):
            raise HTTPException(status_code=400, detail="Body must be a list of decoys")
        
        logger.info(f"📥 Registering {len(decoys)} deployed decoys from node {x_node_id}")
        
        # Validate node access
        node_id = x_node_id
        if AUTH_ENABLED:
            node = await validate_node_access(x_node_id, x_node_key)
            node_id = node["node_id"]
            
            # Update last_seen
            await db_service.update_node_last_seen(
                node_id,
                node_service.update_last_seen(node_id)
            )
        
        # Save each decoy to database
        saved_count = 0
        errors = []
        for decoy in decoys:
            decoy_data = {
                "node_id": node_id,
                "file_name": decoy.get("file_name", "unknown"),
                "file_path": decoy.get("file_path", ""),
                "type": decoy.get("type", "file"),
                "status": "active",
                "triggers_count": 0,
                "created_at": datetime.utcnow().isoformat()
            }
            logger.info(f"Saving decoy: {decoy_data.get('file_name')} to {decoy_data.get('file_path')}")
            try:
                result = await db_service.save_deployed_decoy(decoy_data)
                logger.info(f"Save result: {result}")
                if result:
                    saved_count += 1
                else:
                    errors.append(f"Failed to save {decoy_data.get('file_name')}: returned None")
            except Exception as e:
                logger.error(f"Exception saving decoy: {e}")
                errors.append(str(e))
        
        logger.info(f"✓ Registered {saved_count}/{len(decoys)} decoys for node {node_id}")
        
        response = {
            "status": "success",
            "registered": saved_count,
            "total": len(decoys),
            "node_id": node_id
        }
        if errors:
            response["errors"] = errors
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering decoys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network-event")
async def receive_network_event(
    event: NetworkEvent,
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None),
    x_node_api_key: Optional[str] = Header(None, alias="X-Node-API-Key")
):
    """
    Receive a network connection event from the agent network monitor.

    The agent sends this for suspicious non-standard-port connections.
    If rule_score or ml_risk_score >= ALERT_RISK_THRESHOLD, an alert is created
    and notifications are fired immediately.
    """
    try:
        # Resolve node + user
        user_id = DEMO_USER_ID
        node_id = x_node_id

        if AUTH_ENABLED:
            api_key = x_node_api_key or x_node_key
            if api_key:
                node = await db_service.get_node_by_api_key(api_key)
                if not node:
                    raise HTTPException(status_code=401, detail="Invalid API key")
            else:
                node = await validate_node_access(x_node_id, x_node_key)
            user_id = node["user_id"]
            node_id = node["node_id"]

        event.node_id = node_id
        event.user_id = user_id

        # Persist raw event
        await db_service.save_network_event(event)

        # Determine effective risk score (ML takes priority over rules)
        effective_score = event.ml_risk_score if event.ml_risk_score is not None else event.rule_score
        alert_created = False

        if effective_score >= ALERT_RISK_THRESHOLD:
            attack_type = event.ml_attack_type or (event.rule_triggers[0] if event.rule_triggers else "network_anomaly")

            # Enrich the destination IP (potential C2 / exfiltration target)
            dest_enrichment = await _enrich_ip(event.dest_ip)
            extra: Dict[str, Any] = {"dest_ip_info": dest_enrichment}
            if event.process_name:
                extra["process_name"] = event.process_name

            alert = Alert(
                timestamp=event.timestamp,
                source_ip=event.source_ip,
                service=f"network:{event.protocol}:{event.dest_port}",
                attack_type=attack_type,
                risk_score=effective_score,
                confidence=event.ml_confidence if event.ml_confidence is not None else 0.85,
                activity=f"Suspicious connection to {event.dest_ip}:{event.dest_port}",
                payload=", ".join(event.rule_triggers),
                node_id=node_id,
                user_id=user_id,
                extra=extra,
            )
            await db_service.create_alert(alert)
            alert_created = True
            asyncio.create_task(notification_service.broadcast_alert(alert))

        return {
            "status": "success",
            "alert_created": alert_created,
            "effective_score": effective_score
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing network event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/block-confirmed")
async def agent_block_confirmed(
    node_id: str,
    ip_address: str,
    x_node_api_key: Optional[str] = Header(None, alias="X-Node-API-Key"),
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Agent reports that it has successfully applied a firewall rule for an IP.

    Updates the blocked_ips record status from 'pending' → 'active'.
    """
    try:
        if AUTH_ENABLED:
            api_key = x_node_api_key or x_node_key
            if api_key:
                node = await db_service.get_node_by_api_key(api_key)
                if not node:
                    raise HTTPException(status_code=401, detail="Invalid API key")
                node_id = node["node_id"]
            else:
                node = await validate_node_access(x_node_id, x_node_key)
                node_id = node["node_id"]

        confirmed = await db_service.confirm_block(node_id, ip_address)
        return {"status": "success", "confirmed": confirmed, "ip_address": ip_address}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming block: {e}")
        raise HTTPException(status_code=500, detail=str(e))