"""
Node Management Routes
CRUD operations for nodes
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime
import logging
import json
import io
from pathlib import Path

from backend.models.log_models import NodeCreate, NodeResponse, NodeCreateResponse, NodeUpdate, DecoyResponse
from backend.services.db_service import db_service
from backend.services.node_service import node_service
from backend.config import AUTH_ENABLED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nodes", tags=["nodes"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    from backend.services.auth_service import auth_service
    from backend.config import DEMO_USER_ID
    
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


@router.post("", response_model=NodeCreateResponse)
async def create_node(
    node: NodeCreate,
    authorization: Optional[str] = Header(None)
):
    """
    Create new node
    
    Returns node_id and node_api_key for authentication
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Create node
        node_data = node_service.create_node_data(user_id, node.name)
        result = await db_service.create_node(node_data)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create node")
        
        return NodeCreateResponse(**node_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[NodeResponse])
async def list_nodes(authorization: Optional[str] = Header(None)):
    """
    List all nodes for authenticated user

    Returns user-scoped node list
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get nodes for user
        nodes = await db_service.get_nodes_by_user(user_id)
        
        return [NodeResponse(**node) for node in nodes]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.patch("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: str,
    update: NodeUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update node status
    
    Validates ownership before updating
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Update status
        await db_service.update_node_status(node_id, update.status)
        
        # Get updated node
        updated_node = await db_service.get_node_by_id(node_id)
        
        return NodeResponse(**updated_node)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{node_id}")
async def delete_node(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Delete node
    
    Validates ownership before deleting
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Delete node
        await db_service.delete_node(node_id)
        
        return {"status": "success", "message": f"Node {node_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{node_id}/decoys", response_model=List[DecoyResponse])
async def get_node_decoys(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get all decoy files for a node
    
    Returns list of honeytoken files with access timestamps
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Get decoys
        decoys = await db_service.get_decoys_by_node(node_id)
        
        return [DecoyResponse(**decoy) for decoy in decoys]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting decoys: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{node_id}/agent-download")
async def download_agent(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Download agent installer with embedded configuration
    
    Returns agent.exe with node_id and node_api_key embedded in config.json
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Create config with node_id and node_api_key
        config = {
            "node_id": node["node_id"],
            "node_api_key": node["node_api_key"],
            "node_name": node["name"],
            "backend_url": "https://ml-modle-v0-1.onrender.com/api",
            "ml_service_url": "https://ml-modle-v0-2.onrender.com"
        }
        
        # For now, return config as JSON file
        # In production, this would return a compiled agent.exe
        config_json = json.dumps(config, indent=2)
        
        return FileResponse(
            io.BytesIO(config_json.encode()),
            media_type="application/json",
            filename=f"agent_config_{node_id}.json"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_node_stats(authorization: Optional[str] = Header(None)):
    """
    Get node statistics (total, online, offline)
    
    Returns aggregated node status for user
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get all user nodes
        nodes = await db_service.get_nodes_by_user(user_id)
        
        total = len(nodes)
        online = sum(1 for node in nodes if node.get("status") == "online")
        offline = total - online
        
        return {
            "total": total,
            "online": online,
            "offline": offline
        }
    except Exception as e:
        logger.error(f"Error getting node stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))