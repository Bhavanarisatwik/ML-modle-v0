"""
Agent Routes
Endpoints for endpoint agent events with node validation
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from datetime import datetime
from typing import Optional
import logging
import json
import zipfile
import io
from pathlib import Path

from backend.models.log_models import AgentEvent, Alert
from backend.services.db_service import db_service
from backend.services.ml_service import ml_service
from backend.services.node_service import node_service
from backend.services.node_auth import validate_node_access
from backend.config import ALERT_RISK_THRESHOLD, AUTH_ENABLED, DEMO_USER_ID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/agent-alert")
async def receive_agent_event(
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
        
        # Step 5: Create alert if high risk
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
                user_id=user_id
            )
            await db_service.create_alert(alert)
            alert_created = True
        
        # Step 6: Update attacker profile (use hostname as IP)
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
    node_id: str,
    hostname: str,
    os: str,
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Agent heartbeat (keep-alive ping)
    
    Headers:
    - X-Node-Id: Node ID from config
    - X-Node-Key: Node API key from config
    
    Updates node last_seen and status
    """
    try:
        if AUTH_ENABLED:
            try:
                node = await validate_node_access(x_node_id, x_node_key)
                node_id = node["node_id"]
            except HTTPException:
                raise HTTPException(status_code=401, detail="Invalid node credentials")
        
        # Update node last_seen
        await db_service.update_node(node_id, {
            "last_seen": datetime.utcnow().isoformat(),
            "agent_status": "online"
        })
        
        return {
            "status": "success",
            "message": "Heartbeat received"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
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
            "backend_url": "https://api.decoyverse.example.com",
            "version": "2.0.0",
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
        return FileResponse(
            iter([zip_buffer.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=decoyverse-agent-{node_id}.zip"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))