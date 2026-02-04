"""
Agent Routes
Endpoints for endpoint agent events with node validation
"""

from fastapi import APIRouter, HTTPException, Header
from datetime import datetime
from typing import Optional
import logging

from models.log_models import AgentEvent, Alert
from services.db_service import db_service
from services.ml_service import ml_service
from services.node_service import node_service
from services.node_auth import validate_node_access
from config import ALERT_RISK_THRESHOLD, AUTH_ENABLED, DEMO_USER_ID

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