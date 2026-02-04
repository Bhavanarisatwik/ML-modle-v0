"""
Decoys Routes
Deception asset management (decoys, honeytokens, honeypots)
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
import logging

from models.log_models import DecoyResponse
from services.db_service import db_service
from services.auth_service import auth_service
from config import AUTH_ENABLED, DEMO_USER_ID, DECOYS_COLLECTION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/decoys", tags=["decoys"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


class DecoyModel:
    """Decoy data model"""
    def __init__(self, doc):
        self.id = str(doc.get("_id", ""))
        self.node_id = doc.get("node_id", "")
        self.file_name = doc.get("file_name", "")
        self.type = doc.get("type", "file")  # service, file, port, honeytoken
        self.status = doc.get("status", "active")
        self.triggers_count = doc.get("triggers_count", 0)
        self.last_triggered = doc.get("last_triggered", None)
        self.port = doc.get("port", None)

    def to_dict(self):
        return {
            "id": self.id,
            "node_id": self.node_id,
            "type": self.type,
            "status": self.status,
            "triggers_count": self.triggers_count,
            "last_triggered": self.last_triggered,
            "port": self.port,
            "file_name": self.file_name
        }


@router.get("", response_model=List[dict])
async def get_decoys(
    limit: int = 50,
    authorization: Optional[str] = Header(None)
):
    """
    Get all decoys for authenticated user
    
    Returns: List of decoys with type, status, trigger counts
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Get user's nodes
        nodes = await db_service.get_nodes_by_user(user_id)
        node_ids = [n.get("node_id") for n in nodes]
        
        # Get all decoys for user's nodes
        if not node_ids:
            return []
        
        decoys = await db_service.get_user_decoys(node_ids, limit)
        
        return [DecoyModel(d).to_dict() for d in decoys]
    except Exception as e:
        logger.error(f"Error getting decoys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node/{node_id}")
async def get_node_decoys(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get all decoys for a specific node
    
    Returns: List of decoys for the node
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Verify user owns this node
        node = await db_service.get_node_by_id(node_id)
        if not node or (AUTH_ENABLED and node.get("user_id") != user_id):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get decoys
        decoys = await db_service.get_decoys_by_node(node_id)
        
        return [DecoyModel(d).to_dict() for d in decoys]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node decoys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{decoy_id}")
async def update_decoy_status(
    decoy_id: str,
    status: str,
    authorization: Optional[str] = Header(None)
):
    """
    Toggle decoy status (active/inactive)
    
    Body: { "status": "active" | "inactive" }
    """
    try:
        if status not in ["active", "inactive"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        result = await db_service.update_decoy_status(decoy_id, status)
        
        if not result:
            raise HTTPException(status_code=404, detail="Decoy not found")
        
        return {"success": True, "decoy_id": decoy_id, "new_status": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating decoy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{decoy_id}")
async def delete_decoy(
    decoy_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Delete a decoy
    """
    try:
        result = await db_service.delete_decoy(decoy_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Decoy not found")
        
        return {"success": True, "decoy_id": decoy_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting decoy: {e}")
        raise HTTPException(status_code=500, detail=str(e))
