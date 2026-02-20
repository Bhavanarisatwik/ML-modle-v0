"""
Decoys Routes
Deception asset management (decoys, honeytokens, honeypots)
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
import logging

from backend.models.log_models import DecoyResponse
from backend.services.db_service import db_service
from backend.services.auth_service import auth_service
from backend.config import AUTH_ENABLED, DEMO_USER_ID, DECOYS_COLLECTION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/decoys", tags=["decoys"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


class DecoyModel:
    """Decoy data model"""
    def __init__(self, doc, node_name: str = None):
        self.id = str(doc.get("_id", ""))
        self.node_id = doc.get("node_id", "")
        self.node_name = node_name or doc.get("node_name", "")
        self.file_name = doc.get("file_name", "")
        self.file_path = doc.get("file_path", "")
        self.type = doc.get("type", "file")  # service, file, port, honeytoken
        self.status = doc.get("status", "active")
        self.triggers_count = doc.get("triggers_count", 0)
        self.last_triggered = doc.get("last_triggered", None)
        self.port = doc.get("port", None)
        self.created_at = doc.get("created_at", None)

    def to_dict(self):
        return {
            "id": self.id,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "type": self.type,
            "status": self.status,
            "triggers_count": self.triggers_count,
            "last_triggered": self.last_triggered,
            "port": self.port,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "created_at": self.created_at
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
        node_ids = [str(n.get("node_id", "")) for n in nodes if n.get("node_id")]
        
        # Create node_id -> node_name mapping
        node_names = {n.get("node_id"): n.get("name", "") for n in nodes}
        
        # Get all decoys for user's nodes
        if not node_ids:
            return []
        
        decoys = await db_service.get_user_decoys(node_ids, limit)
        
        # Add node_name to each decoy
        return [DecoyModel(d, node_names.get(d.get("node_id"), "")).to_dict() for d in decoys]
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

from pydantic import BaseModel
class DeployRequest(BaseModel):
    node_id: str
    count: int

@router.post("/deploy")
async def deploy_decoys(
    request: DeployRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Increase the honeytoken count for a node to trigger creation on the agent's next check-in
    """
    try:
        user_id = get_user_id_from_header(authorization)
        node = await db_service.get_node_by_id(request.node_id)
        if not node or (AUTH_ENABLED and node.get("user_id") != user_id):
            raise HTTPException(status_code=403, detail="Unauthorized")

        # Increment honeytoken count in deployment config
        if "deployment_config" not in node:
            node["deployment_config"] = {"initial_decoys": 3, "initial_honeytokens": 5}
        
        node["deployment_config"]["initial_honeytokens"] = node["deployment_config"].get("initial_honeytokens", 5) + request.count
        
        # Update node
        # A proper update method would be better, but we'll use a direct update here if the service lacks one
        await db_service.db["nodes"].update_one(
            {"node_id": request.node_id},
            {"$set": {"deployment_config": node["deployment_config"]}}
        )
        
        return {"success": True, "data": []} # Data will populate next time agent reports
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering deploy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

