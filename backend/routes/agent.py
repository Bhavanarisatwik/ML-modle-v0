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
from config import ALERT_RISK_THRESHOLD, AUTH_ENABLED, DEMO_USER_ID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/agent-alert")
async def receive_agent_event(
    event: AgentEvent,
    x_node_key: Optional[str] = Header(None)
):
    """
    Receive honeytoken trigger event from endpoint agents
    
    Headers:
    - X-Node-Key: Node API key for authentication (required if AUTH_ENABLED)
    
    Flow:
    1. Validate node_id and API key (if AUTH_ENABLED)
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
        node_id = event.node_id
        
        if AUTH_ENABLED:
            if not event.node_id:
                raise HTTPException(
                    status_code=400,
                    detail="node_id is required when AUTH_ENABLED=True"
                )
            
            if not x_node_key:
                raise HTTPException(
                    status_code=401,
                    detail="X-Node-Key header is required for authentication"
                )
            
            # Validate node exists
            node = await db_service.get_node_by_id(event.node_id)
            if not node:
                raise HTTPException(
                    status_code=404,
                    detail=f"Node {event.node_id} not found"
                )
            
            # Validate API key
            if node.get("api_key") != x_node_key:
                logger.warning(f"Invalid API key attempt for node {event.node_id}")
                raise HTTPException(
                    status_code=403,
                    detail="Invalid node API key"
                )
            
            # Check node is active
            if node["status"] != "active":
                raise HTTPException(
                    status_code=403,
                    detail=f"Node {event.node_id} is inactive"
                )
            
            user_id = node["user_id"]
            
            # Update node last_seen
            await db_service.update_node_last_seen(
                event.node_id,
                node_service.update_last_seen(event.node_id)
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
        ml_prediction = await ml_service.predict_attack(event.dict())
        
        if ml_prediction:
            logger.info(f"🧠 ML Prediction: {ml_prediction.attack_type} (Risk: {ml_prediction.risk_score}/10)")
        else:
            logger.warning("⚠️ ML prediction failed, saving event without prediction")
        
        # Step 4: Save event to database
        event_id = await db_service.save_agent_event(
            event.dict(),
            ml_prediction.dict() if ml_prediction else None
        )
        
        # Step 5: Create alert if high risk
        alert_created = False
        if ml_prediction and ml_prediction.risk_score > ALERT_RISK_THRESHOLD:
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
