"""
Honeytokens Routes
Honeytoken tracking and management (special decoys with type="honeytoken")
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
import logging

from backend.services.db_service import db_service
from backend.services.auth_service import auth_service
from backend.config import AUTH_ENABLED, DEMO_USER_ID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/honeytokels", tags=["honeytokels"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


class HoneytokenModel:
    """Honeytoken data model"""
    def __init__(self, doc):
        self.id = str(doc.get("_id", ""))
        self.node_id = doc.get("node_id", "")
        self.file_name = doc.get("file_name", "")
        self.type = doc.get("type", "honeytoken")
        self.status = doc.get("status", "active")
        self.triggers_count = doc.get("triggers_count", 0)
        self.last_triggered = doc.get("last_triggered", None)
        self.download_count = doc.get("download_count", 0)

    def to_dict(self):
        return {
            "id": self.id,
            "node_id": self.node_id,
            "file_name": self.file_name,
            "type": "honeytoken",
            "status": self.status,
            "download_count": self.download_count,
            "trigger_count": self.triggers_count,
            "last_triggered": self.last_triggered
        }


@router.get("", response_model=List[dict])
async def get_honeytokels(
    limit: int = 50,
    authorization: Optional[str] = Header(None)
):
    """
    Get all honeytokels for authenticated user
    
    Honeytokels are decoys with type="honeytoken"
    
    Returns: List of honeytokels with download/trigger counts
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Get user's nodes
        nodes = await db_service.get_nodes_by_user(user_id)
        node_ids = [str(n.get("node_id", "")) for n in nodes if n.get("node_id")]
        
        # Get all honeytokels for user's nodes
        if not node_ids:
            return []
        
        honeytokels = await db_service.get_user_honeytokels(node_ids, limit)
        
        return [HoneytokenModel(h).to_dict() for h in honeytokels]
    except Exception as e:
        logger.error(f"Error getting honeytokels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node/{node_id}")
async def get_node_honeytokels(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get all honeytokels for a specific node
    
    Returns: List of honeytokels for the node
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Verify user owns this node
        node = await db_service.get_node_by_id(node_id)
        if not node or (AUTH_ENABLED and node.get("user_id") != user_id):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get honeytokels (decoys with type="honeytoken")
        honeytokels = await db_service.get_node_honeytokels(node_id)
        
        return [HoneytokenModel(h).to_dict() for h in honeytokels]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node honeytokels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{honeytoken_id}")
async def update_honeytoken_status(
    honeytoken_id: str,
    status: str,
    authorization: Optional[str] = Header(None)
):
    """
    Toggle honeytoken status (active/inactive)
    
    Body: { "status": "active" | "inactive" }
    """
    try:
        if status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        result = await db_service.update_honeytoken_status(honeytoken_id, status)
        
        if not result:
            raise HTTPException(status_code=404, detail="Honeytoken not found")
        
        return {"success": True, "honeytoken_id": honeytoken_id, "new_status": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating honeytoken: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{honeytoken_id}")
async def delete_honeytoken(
    honeytoken_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Delete a honeytoken
    """
    try:
        result = await db_service.delete_honeytoken(honeytoken_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Honeytoken not found")
        
        return {"success": True, "honeytoken_id": honeytoken_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting honeytoken: {e}")
        raise HTTPException(status_code=500, detail=str(e))
