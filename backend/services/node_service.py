"""
Node Service
Node management and validation
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import uuid
import secrets

logger = logging.getLogger(__name__)


class NodeService:
    """Node management service"""
    
    @staticmethod
    def generate_node_id() -> str:
        """Generate unique node ID"""
        return f"node-{uuid.uuid4().hex[:16]}"
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate secure API key for node authentication"""
        return f"nk_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def create_node_data(user_id: str, name: str, os_type: str = "windows", deployment_config: Optional[Dict] = None) -> Dict[str, Any]:
        """Create node document for MongoDB"""
        now = datetime.utcnow().isoformat()
        
        # Default deployment config
        default_config = {
            "initial_decoys": 3,
            "initial_honeytokens": 5,
            "deploy_path": None
        }
        
        if deployment_config:
            default_config.update(deployment_config)
        
        return {
            "node_id": NodeService.generate_node_id(),
            "user_id": user_id,
            "name": name,
            "os_type": os_type or "windows",
            "status": "active",
            "ip_address": None,  # Set when agent first connects
            "node_api_key": NodeService.generate_api_key(),
            "last_seen": None,
            "created_at": now,
            "deployment_config": default_config,
            "deployed_decoys": [],
            "deployed_honeytokens": []
        }
    
    @staticmethod
    def update_last_seen(node_id: str) -> str:
        """Get current timestamp for last_seen update"""
        return datetime.utcnow().isoformat()


# Singleton instance
node_service = NodeService()
