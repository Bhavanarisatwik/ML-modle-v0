"""
Agent Configuration and Registration Module
Handles node_id, node_api_key, and backend communication
"""

import json
import os
import socket
import platform
import logging
from pathlib import Path
from typing import Dict, Optional
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentConfig")


class AgentConfig:
    """Manages agent configuration and registration"""
    
    CONFIG_FILE = "agent_config.json"
    
    def __init__(self):
        """Initialize agent configuration"""
        self.config: Dict = {}
        self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from file"""
        try:
            if Path(self.CONFIG_FILE).exists():
                with open(self.CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"✓ Configuration loaded: {self.config.get('node_name')}")
                return True
            else:
                logger.warning(f"Configuration file not found: {self.CONFIG_FILE}")
                return False
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False
    
    def save_config(self) -> bool:
        """Save configuration to file"""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"✓ Configuration saved")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def get_node_id(self) -> Optional[str]:
        """Get node_id from config"""
        return self.config.get("node_id")
    
    def get_node_api_key(self) -> Optional[str]:
        """Get node_api_key from config"""
        return self.config.get("node_api_key")
    
    def get_backend_url(self) -> str:
        """Get backend API URL"""
        return self.config.get(
            "backend_url",
            "https://ml-modle-v0-1.onrender.com/api"
        )
    
    def get_deployment_config(self) -> Dict:
        """Get deployment configuration (initial decoys/honeytokens)"""
        return self.config.get("deployment_config", {
            "initial_decoys": 3,
            "initial_honeytokens": 5,
            "deploy_path": None
        })
    
    def is_registered(self) -> bool:
        """Check if agent is registered"""
        return bool(self.get_node_id() and self.get_node_api_key())
    
    @staticmethod
    def get_system_info() -> Dict:
        """Gather system information"""
        try:
            hostname = socket.gethostname()
            os_name = platform.system()
            os_version = platform.release()
            
            return {
                "hostname": hostname,
                "os": f"{os_name} {os_version}",
                "platform": platform.platform()
            }
        except Exception as e:
            logger.warning(f"Failed to gather system info: {e}")
            return {"hostname": "unknown", "os": "unknown"}


class AgentRegistration:
    """Handles agent registration with backend"""
    
    def __init__(self, config: AgentConfig):
        """Initialize registration handler"""
        self.config = config
        self.backend_url = config.get_backend_url()
    
    def register(self, node_id: str, node_api_key: str) -> bool:
        """
        Register agent with backend
        
        Args:
            node_id: Node ID from config
            node_api_key: Node API key from config
        
        Returns:
            True if registration successful
        """
        try:
            system_info = AgentConfig.get_system_info()
            
            payload = {
                "node_id": node_id,
                "node_api_key": node_api_key,
                **system_info
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Node-Id": node_id,
                "X-Node-Key": node_api_key,
            }
            
            # Register endpoint
            url = f"{self.backend_url}/agent/register"
            
            logger.info(f"📤 Registering node {node_id}...")
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✓ Node registered successfully")
                return True
            else:
                logger.error(f"✗ Registration failed: {response.status_code}")
                logger.error(f"  Response: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"✗ Registration error: {e}")
            return False
    
    def send_heartbeat(self, node_id: str, node_api_key: str) -> bool:
        """
        Send heartbeat to backend (keep-alive)
        
        Args:
            node_id: Node ID from config
            node_api_key: Node API key from config
        
        Returns:
            True if heartbeat successful
        """
        try:
            system_info = AgentConfig.get_system_info()
            
            payload = {
                "node_id": node_id,
                **system_info
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Node-Id": node_id,
                "X-Node-Key": node_api_key,
            }
            
            url = f"{self.backend_url}/agent/heartbeat"
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            return response.status_code in [200, 201]
        
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            return False
    
    def register_deployed_decoys(self, node_id: str, node_api_key: str, decoys: list) -> bool:
        """
        Register deployed decoys with backend
        
        Args:
            node_id: Node ID from config
            node_api_key: Node API key from config
            decoys: List of deployed decoy dicts with file_name, file_path, type
        
        Returns:
            True if registration successful
        """
        try:
            if not decoys:
                logger.info("No decoys to register")
                return True
            
            headers = {
                "Content-Type": "application/json",
                "X-Node-Id": node_id,
                "X-Node-Key": node_api_key,
            }
            
            url = f"{self.backend_url}/agent/register-decoys"
            
            logger.info(f"📤 Registering {len(decoys)} deployed decoys...")
            response = requests.post(
                url,
                json=decoys,
                headers=headers,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"✓ Registered {result.get('registered', 0)} decoys with backend")
                return True
            else:
                logger.warning(f"⚠️ Decoy registration returned: {response.status_code}")
                return False
        
        except Exception as e:
            logger.warning(f"Decoy registration failed: {e}")
            return False


def ensure_agent_registered(config: AgentConfig) -> bool:
    """
    Ensure agent is registered before running
    
    Args:
        config: AgentConfig instance
    
    Returns:
        True if registered or successfully registered
    """
    if config.is_registered():
        node_id = config.get_node_id()
        node_api_key = config.get_node_api_key()
        
        if not node_id or not node_api_key:
            logger.error("✗ Node ID or API key is missing!")
            return False
        
        logger.info(f"✓ Agent registered as: {node_id}")
        
        # Send heartbeat
        registration = AgentRegistration(config)
        registration.send_heartbeat(
            node_id,
            node_api_key
        )
        
        return True
    else:
        logger.error("✗ Agent not registered!")
        logger.error("  Please ensure agent_config.json exists with node_id and node_api_key")
        logger.error("  You can download it from the DecoyVerse dashboard")
        return False
