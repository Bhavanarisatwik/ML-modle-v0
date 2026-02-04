"""
Logs/Events Routes
Security event log queries with filtering and search
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
import logging
from datetime import datetime

from services.db_service import db_service
from services.auth_service import auth_service
from config import AUTH_ENABLED, DEMO_USER_ID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["logs"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


class EventModel:
    """Security event model"""
    def __init__(self, doc):
        self.id = str(doc.get("_id", ""))
        self.timestamp = doc.get("timestamp", "")
        self.node_id = doc.get("node_id", "")
        self.event_type = doc.get("activity", "") or doc.get("event_type", "")
        self.source_ip = doc.get("source_ip", "")
        self.severity = doc.get("severity", "MEDIUM").lower()
        self.related_decoy = doc.get("file_accessed", "") or doc.get("related_decoy", "")
        self.risk_score = doc.get("risk_score", 50)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "node_id": self.node_id,
            "event_type": self.event_type,
            "source_ip": self.source_ip,
            "severity": self.severity,
            "related_decoy": self.related_decoy,
            "risk_score": self.risk_score
        }


@router.get("")
async def get_logs(
    limit: int = 100,
    node_id: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """
    Get security event logs with filtering
    
    Query params:
    - limit: max results (default 100)
    - node_id: filter by node ID
    - severity: filter by severity (low, medium, high, critical)
    - search: search by source_ip, event_type, or related_decoy
    
    Returns: List of security events with timestamp, severity, risk_score
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Get user's nodes
        nodes = await db_service.get_nodes_by_user(user_id)
        node_ids = [n.get("node_id") for n in nodes]
        
        if not node_ids:
            return []
        
        # Get events (honeypot logs + agent events)
        events = await db_service.get_user_events(node_ids, limit)
        
        # Filter by node_id if specified
        if node_id:
            events = [e for e in events if e.get("node_id") == node_id]
        
        # Filter by severity if specified
        if severity:
            severity_lower = severity.lower()
            events = [e for e in events if e.get("severity", "").lower() == severity_lower]
        
        # Search filter
        if search:
            search_lower = search.lower()
            events = [
                e for e in events
                if search_lower in e.get("source_ip", "").lower() or
                   search_lower in e.get("activity", "").lower() or
                   search_lower in e.get("event_type", "").lower() or
                   search_lower in e.get("file_accessed", "").lower() or
                   search_lower in e.get("related_decoy", "").lower()
            ]
        
        return [EventModel(e).to_dict() for e in events]
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node/{node_id}")
async def get_node_logs(
    node_id: str,
    limit: int = 100,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """
    Get logs for a specific node
    
    Returns: List of events for the node
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Verify user owns this node
        node = await db_service.get_node_by_id(node_id)
        if not node or (AUTH_ENABLED and node.get("user_id") != user_id):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get node events
        events = await db_service.get_node_events(node_id, limit)
        
        # Apply filters
        if severity:
            severity_lower = severity.lower()
            events = [e for e in events if e.get("severity", "").lower() == severity_lower]
        
        if search:
            search_lower = search.lower()
            events = [
                e for e in events
                if search_lower in e.get("source_ip", "").lower() or
                   search_lower in e.get("activity", "").lower()
            ]
        
        return [EventModel(e).to_dict() for e in events]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
