"""
Alerts Routes
Dashboard endpoints with user scoping
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
import logging
from pydantic import BaseModel

from datetime import datetime
from backend.models.log_models import StatsResponse, Alert, BlockedIP
from backend.services.db_service import db_service
from backend.services.auth_service import auth_service
from backend.config import AUTH_ENABLED, DEMO_USER_ID


class AlertStatusUpdate(BaseModel):
    status: str

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["alerts"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


@router.get("/stats", response_model=StatsResponse)
async def get_stats(authorization: Optional[str] = Header(None)):
    """
    Get dashboard statistics for authenticated user
    
    Returns aggregated stats for user's nodes and alerts
    """
    try:
        # Get user_id from token (or demo user if AUTH_ENABLED=False)
        user_id = get_user_id_from_header(authorization)
        
        # Get user-scoped stats
        stats = await db_service.get_user_stats(user_id)
        
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent-attacks", response_model=List[Alert])
async def get_recent_attacks(
    limit: int = 10,
    authorization: Optional[str] = Header(None)
):
    """
    Get recent high-risk attacks
    
    Returns user-scoped alert list
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Get recent alerts
        alerts = await db_service.get_recent_alerts(limit=limit, user_id=user_id)
        
        return [Alert(**alert) for alert in alerts]
    except Exception as e:
        logger.error(f"Error getting recent attacks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=List[Alert])
async def get_all_alerts(
    limit: int = 50,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """
    Get all alerts for user with optional filters
    
    Query params:
    - severity: critical, high, medium, low
    - status: open, investigating, resolved
    - limit: max results (default 50)
    
    Returns user-scoped filtered alert list
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Get all alerts
        alerts = await db_service.get_recent_alerts(limit=limit, user_id=user_id)
        
        # Apply filters
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]
        if status:
            alerts = [a for a in alerts if a.get("status") == status]
        
        return [Alert(**alert) for alert in alerts]
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/alerts/{alert_id}")
async def update_alert_status(
    alert_id: str,
    update_data: AlertStatusUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update alert status

    Body: { "status": "resolved" | "investigating" | "open" }
    """
    try:
        if update_data.status not in ["open", "investigating", "resolved"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        result = await db_service.update_alert_status(alert_id, update_data.status)

        if not result:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"success": True, "alert_id": alert_id, "new_status": update_data.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attacker-profile/{source_ip}")
async def get_attacker_profile(
    source_ip: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get attacker profile information
    
    Returns compiled threat intelligence for source IP
    """
    try:
        # Get profile
        profile = await db_service.get_attacker_profile(source_ip)
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting attacker profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BlockIPRequest(BaseModel):
    ip_address: str
    node_id: str
    alert_id: Optional[str] = None


@router.post("/block-ip")
async def block_ip(
    request: BlockIPRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Queue an IP address for firewall blocking on the specified node.

    The agent picks up pending blocks on its next heartbeat and applies
    the Windows Firewall rule via the dv_firewall helper (privilege-separated).
    """
    try:
        user_id = get_user_id_from_header(authorization)

        block = BlockedIP(
            node_id=request.node_id,
            ip_address=request.ip_address,
            requested_at=datetime.utcnow().isoformat(),
            requested_by_user_id=user_id,
            alert_id=request.alert_id,
            status="pending"
        )
        block_id = await db_service.add_blocked_ip(block)

        if not block_id:
            raise HTTPException(status_code=500, detail="Failed to queue IP block")

        return {
            "success": True,
            "message": f"IP {request.ip_address} queued for blocking on node {request.node_id}",
            "block_id": block_id,
            "status": "pending"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing IP block: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocked-ips")
async def get_blocked_ips(authorization: Optional[str] = Header(None)):
    """
    Return all blocked IPs for the authenticated user's nodes.
    """
    try:
        user_id = get_user_id_from_header(authorization)
        blocked = await db_service.get_blocked_ips(user_id)
        return {"success": True, "data": blocked}
    except Exception as e:
        logger.error(f"Error getting blocked IPs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint with database status"""
    db_connected = db_service.db is not None
    
    # Try a test operation
    test_result = "not_tested"
    if db_connected:
        try:
            # Try to ping the database
            await db_service.db.command("ping")
            test_result = "ping_success"
        except Exception as e:
            test_result = f"ping_failed: {str(e)}"
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "connected" if db_connected else "disconnected",
        "db_test": test_result,
        "auth_enabled": AUTH_ENABLED
    }
