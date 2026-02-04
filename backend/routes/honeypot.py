"""
Honeypot Routes
Endpoints for honeypot log ingestion with node validation
"""

from fastapi import APIRouter, HTTPException, Header
from datetime import datetime
from typing import Optional
import logging

from models.log_models import HoneypotLog, Alert
from services.db_service import db_service
from services.ml_service import ml_service
from services.node_service import node_service
from services.node_auth import validate_node_access
from config import ALERT_RISK_THRESHOLD, AUTH_ENABLED, DEMO_USER_ID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["honeypot"])


@router.post("/honeypot-log")
async def receive_honeypot_log(
    log: HoneypotLog,
    x_node_id: Optional[str] = Header(None),
    x_node_key: Optional[str] = Header(None)
):
    """
    Receive honeypot log from SSH/FTP/Web honeypots
    
    Headers:
    - X-Node-Id: Node ID for authentication (required if AUTH_ENABLED)
    - X-Node-Key: Node API key for authentication (required if AUTH_ENABLED)
    
    Flow:
    1. Validate X-Node-Id and X-Node-Key (if AUTH_ENABLED)
    2. Update node.last_seen
    3. Call ML API for prediction
    4. Save log + prediction to MongoDB
    5. If risk_score > 7, create alert with node_id and user_id
    6. Update attacker profile
    7. Return response
    """
    try:
        logger.info(f"📥 Honeypot log received: {log.service} from {log.source_ip}")
        
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
        
        # Step 2: Get ML prediction
        log_data = log.dict()
        log_data["node_id"] = node_id
        ml_prediction = await ml_service.predict_attack(log_data)
        
        if ml_prediction:
            logger.info(f"🧠 ML Prediction: {ml_prediction.attack_type} (Risk: {ml_prediction.risk_score}/10)")
        else:
            logger.warning("⚠️ ML prediction failed, saving log without prediction")
        
        # Step 3: Save log to database
        log_id = await db_service.save_honeypot_log(
            log_data,
            ml_prediction.dict() if ml_prediction else None
        )
        
        # Step 4: Create alert if high risk
        alert_created = False
        if ml_prediction and ml_prediction.risk_score >= ALERT_RISK_THRESHOLD:
            alert = Alert(
                alert_id=f"ALERT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{log.source_ip[:8]}",
                timestamp=log.timestamp,
                source_ip=log.source_ip,
                service=log.service,
                attack_type=ml_prediction.attack_type,
                risk_score=ml_prediction.risk_score,
                confidence=ml_prediction.confidence,
                activity=log.activity,
                payload=log.payload,
                node_id=node_id,
                user_id=user_id
            )
            await db_service.create_alert(alert)
            alert_created = True
        
        # Step 5: Update attacker profile
        if ml_prediction:
            await db_service.update_attacker_profile(
                source_ip=log.source_ip,
                attack_type=ml_prediction.attack_type,
                risk_score=ml_prediction.risk_score,
                service=log.service
            )
        
        return {
            "status": "success",
            "log_id": log_id,
            "ml_prediction": ml_prediction.dict() if ml_prediction else None,
            "alert_created": alert_created
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing honeypot log: {e}")
        raise HTTPException(status_code=500, detail=str(e))
