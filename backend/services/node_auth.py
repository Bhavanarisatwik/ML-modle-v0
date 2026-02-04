"""
Node Authentication Utilities
Validates node API key and status for ingestion
"""

from fastapi import HTTPException
from typing import Dict, Any
import logging

from backend.services.db_service import db_service

logger = logging.getLogger(__name__)


async def validate_node_access(node_id: str, node_key: str) -> Dict[str, Any]:
    """
    Validate node exists, API key matches, and node is active.
    Returns node document if valid.
    """
    if not node_id:
        raise HTTPException(status_code=400, detail="X-Node-Id header is required")

    if not node_key:
        raise HTTPException(status_code=401, detail="X-Node-Key header is required")

    node = await db_service.get_node_by_id(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    stored_key = node.get("node_api_key") or node.get("api_key")
    if stored_key != node_key:
        logger.warning(f"Invalid API key attempt for node {node_id}")
        raise HTTPException(status_code=401, detail="Invalid node API key")

    if node.get("status") != "active":
        raise HTTPException(status_code=403, detail=f"Node {node_id} is inactive")

    return node
