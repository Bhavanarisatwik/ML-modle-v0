"""
Database Service
MongoDB operations for logs, alerts, profiles, users, and nodes
"""

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from config import (
    MONGODB_URI,
    DATABASE_NAME,
    HONEYPOT_LOGS_COLLECTION,
    AGENT_EVENTS_COLLECTION,
    ALERTS_COLLECTION,
    ATTACKER_PROFILES_COLLECTION,
    USERS_COLLECTION,
    NODES_COLLECTION,
    DECOYS_COLLECTION,
    ALERT_RISK_THRESHOLD,
    AUTH_ENABLED,
    DEMO_USER_ID
)
from models.log_models import Alert, AttackerProfile

logger = logging.getLogger(__name__)


class DatabaseService:
    """MongoDB database operations"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
    
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(MONGODB_URI)
            self.db = self.client[DATABASE_NAME]
            # Test connection
            await self.client.admin.command('ping')
            logger.info("✓ Connected to MongoDB")
        except Exception as e:
            logger.error(f"✗ MongoDB connection failed: {e}")
            logger.warning("Running without database (logs will not be persisted)")
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    # ==================== USER OPERATIONS ====================
    
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        """Create new user"""
        try:
            result = await self.db[USERS_COLLECTION].insert_one(user_data)
            logger.info(f"✓ User created: {user_data['email']}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            user = await self.db[USERS_COLLECTION].find_one({"email": email})
            return user
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            user = await self.db[USERS_COLLECTION].find_one({"id": user_id})
            return user
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    # ==================== NODE OPERATIONS ====================
    
    async def create_node(self, node_data: Dict[str, Any]) -> Optional[str]:
        """Create new node"""
        try:
            result = await self.db[NODES_COLLECTION].insert_one(node_data)
            logger.info(f"✓ Node created: {node_data['node_id']}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            return None
    
    async def get_nodes_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all nodes for a user"""
        try:
            cursor = self.db[NODES_COLLECTION].find({"user_id": user_id})
            nodes = await cursor.to_list(length=1000)
            
            for node in nodes:
                node["_id"] = str(node["_id"])
            
            return nodes
        except Exception as e:
            logger.error(f"Error getting nodes: {e}")
            return []
    
    async def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by ID"""
        try:
            node = await self.db[NODES_COLLECTION].find_one({"node_id": node_id})
            if node:
                node["_id"] = str(node["_id"])
            return node
        except Exception as e:
            logger.error(f"Error getting node: {e}")
            return None
    
    async def update_node_status(self, node_id: str, status: str) -> bool:
        """Update node status"""
        try:
            await self.db[NODES_COLLECTION].update_one(
                {"node_id": node_id},
                {"$set": {"status": status}}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating node status: {e}")
            return False
    
    async def update_node_last_seen(self, node_id: str, timestamp: str) -> bool:
        """Update node last_seen timestamp"""
        try:
            await self.db[NODES_COLLECTION].update_one(
                {"node_id": node_id},
                {"$set": {"last_seen": timestamp}}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating node last_seen: {e}")
            return False
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete node"""
        try:
            await self.db[NODES_COLLECTION].delete_one({"node_id": node_id})
            logger.info(f"✓ Node deleted: {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            return False
    
    # ==================== DECOY OPERATIONS ====================
    
    async def save_decoy_access(self, decoy_data: Dict[str, Any]) -> Optional[str]:
        """Save or update decoy access record"""
        try:
            result = await self.db[DECOYS_COLLECTION].update_one(
                {"node_id": decoy_data["node_id"], "file_name": decoy_data["file_name"]},
                {"$set": decoy_data},
                upsert=True
            )
            return str(result.upserted_id) if result.upserted_id else decoy_data["node_id"]
        except Exception as e:
            logger.error(f"Error saving decoy access: {e}")
            return None
    
    async def get_decoys_by_node(self, node_id: str) -> List[Dict]:
        """Get all decoys for a node"""
        try:
            cursor = self.db[DECOYS_COLLECTION].find({"node_id": node_id})
            decoys = await cursor.to_list(length=1000)
            
            for decoy in decoys:
                decoy["_id"] = str(decoy["_id"])
            
            return decoys
        except Exception as e:
            logger.error(f"Error getting decoys: {e}")
            return []
    
    # ==================== HONEYPOT LOG OPERATIONS ====================
    
    async def save_honeypot_log(self, log_data: Dict[str, Any], ml_prediction: Optional[Dict[str, Any]]) -> Optional[str]:
        """Save honeypot log with ML prediction"""
        try:
            document = {
                **log_data,
                "ml_prediction": ml_prediction,
                "timestamp_saved": datetime.utcnow().isoformat()
            }
            
            result = await self.db[HONEYPOT_LOGS_COLLECTION].insert_one(document)
            logger.info(f"✓ Honeypot log saved: {log_data.get('source_ip')}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error saving honeypot log: {e}")
            return None
    
    # ==================== AGENT EVENT OPERATIONS ====================
    
    async def save_agent_event(self, event_data: Dict[str, Any], ml_prediction: Optional[Dict[str, Any]]) -> Optional[str]:
        """Save agent event with ML prediction"""
        try:
            document = {
                **event_data,
                "ml_prediction": ml_prediction,
                "timestamp_saved": datetime.utcnow().isoformat()
            }
            
            result = await self.db[AGENT_EVENTS_COLLECTION].insert_one(document)
            logger.info(f"✓ Agent event saved: {event_data.get('hostname')}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error saving agent event: {e}")
            return None
    
    # ==================== ALERT OPERATIONS ====================
    
    async def create_alert(self, alert: Alert) -> Optional[str]:
        """Create high-risk alert"""
        try:
            alert_dict = alert.dict()
            result = await self.db[ALERTS_COLLECTION].insert_one(alert_dict)
            logger.warning(f"🚨 ALERT CREATED: {alert.attack_type} from {alert.source_ip}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None
    
    async def get_recent_alerts(self, limit: int = 10, user_id: Optional[str] = None) -> List[Dict]:
        """Get recent alerts"""
        try:
            query = {}
            if AUTH_ENABLED and user_id:
                query = {"user_id": user_id}
            
            cursor = self.db[ALERTS_COLLECTION].find(query).sort("timestamp", -1).limit(limit)
            alerts = await cursor.to_list(length=limit)
            
            for alert in alerts:
                alert["_id"] = str(alert["_id"])
            
            return alerts
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []
    
    # ==================== ATTACKER PROFILE OPERATIONS ====================
    
    async def update_attacker_profile(self, source_ip: str, attack_type: str, risk_score: int, service: str):
        """Update or create attacker profile"""
        try:
            existing = await self.db[ATTACKER_PROFILES_COLLECTION].find_one({"source_ip": source_ip})
            
            if existing:
                # Update existing profile
                total_attacks = existing.get("total_attacks", 0) + 1
                attack_types = existing.get("attack_types", {})
                attack_types[attack_type] = attack_types.get(attack_type, 0) + 1
                
                services_targeted = existing.get("services_targeted", {})
                services_targeted[service] = services_targeted.get(service, 0) + 1
                
                avg_risk = ((existing.get("average_risk_score", 0) * existing.get("total_attacks", 1)) + risk_score) / total_attacks
                
                await self.db[ATTACKER_PROFILES_COLLECTION].update_one(
                    {"source_ip": source_ip},
                    {
                        "$set": {
                            "total_attacks": total_attacks,
                            "average_risk_score": avg_risk,
                            "attack_types": attack_types,
                            "services_targeted": services_targeted,
                            "last_seen": datetime.utcnow().isoformat(),
                            "most_common_attack": max(attack_types, key=attack_types.get) if attack_types else attack_type
                        }
                    }
                )
            else:
                # Create new profile
                profile = AttackerProfile(
                    source_ip=source_ip,
                    total_attacks=1,
                    most_common_attack=attack_type,
                    average_risk_score=risk_score,
                    first_seen=datetime.utcnow().isoformat(),
                    last_seen=datetime.utcnow().isoformat(),
                    attack_types={attack_type: 1},
                    services_targeted={service: 1}
                )
                await self.db[ATTACKER_PROFILES_COLLECTION].insert_one(profile.dict())
            
            logger.info(f"✓ Attacker profile updated: {source_ip}")
        except Exception as e:
            logger.error(f"Error updating attacker profile: {e}")
    
    async def get_attacker_profile(self, source_ip: str) -> Optional[Dict]:
        """Get attacker profile"""
        try:
            profile = await self.db[ATTACKER_PROFILES_COLLECTION].find_one({"source_ip": source_ip})
            if profile:
                profile["_id"] = str(profile["_id"])
            return profile
        except Exception as e:
            logger.error(f"Error getting attacker profile: {e}")
            return None
    
    # ==================== STATISTICS OPERATIONS ====================
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get dashboard statistics for a user"""
        try:
            # Determine filter
            if not AUTH_ENABLED:
                user_filter = {}
            else:
                user_filter = {"user_id": user_id}
            
            # Total nodes
            total_nodes = await self.db[NODES_COLLECTION].count_documents(user_filter)
            
            # Active nodes
            active_filter = {**user_filter, "status": "active"}
            active_nodes = await self.db[NODES_COLLECTION].count_documents(active_filter)
            
            # Total attacks
            total_attacks = await self.db[ALERTS_COLLECTION].count_documents(user_filter)
            
            # Active alerts
            active_alerts = await self.db[ALERTS_COLLECTION].count_documents(user_filter)
            
            # Unique attackers
            pipeline = [
                {"$match": user_filter} if AUTH_ENABLED and user_filter else {"$match": {}},
                {"$group": {"_id": "$source_ip"}}
            ]
            unique_ips = await self.db[ALERTS_COLLECTION].aggregate(pipeline).to_list(1000)
            unique_attackers = len(unique_ips)
            
            # Average risk score
            pipeline = [
                {"$match": user_filter} if AUTH_ENABLED and user_filter else {"$match": {}},
                {"$group": {
                    "_id": None,
                    "avg_risk": {"$avg": "$risk_score"},
                    "high_risk_count": {
                        "$sum": {
                            "$cond": [{"$gte": ["$risk_score", ALERT_RISK_THRESHOLD]}, 1, 0]
                        }
                    }
                }}
            ]
            
            result = await self.db[ALERTS_COLLECTION].aggregate(pipeline).to_list(1)
            avg_risk_score = result[0]["avg_risk"] if result and result[0].get("avg_risk") else 0.0
            high_risk_count = result[0]["high_risk_count"] if result else 0
            
            # Recent risk average (last 10 alerts)
            recent_alerts = await self.get_recent_alerts(limit=10, user_id=user_id)
            recent_risk_average = sum([a.get("risk_score", 0) for a in recent_alerts]) / len(recent_alerts) if recent_alerts else 0.0
            
            return {
                "total_attacks": total_attacks,
                "active_alerts": active_alerts,
                "unique_attackers": unique_attackers,
                "avg_risk_score": round(avg_risk_score, 1),
                "high_risk_count": high_risk_count,
                "total_nodes": total_nodes,
                "active_nodes": active_nodes,
                "recent_risk_average": round(recent_risk_average, 1)
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "total_attacks": 0,
                "active_alerts": 0,
                "unique_attackers": 0,
                "avg_risk_score": 0.0,
                "high_risk_count": 0,
                "total_nodes": 0,
                "active_nodes": 0,
                "recent_risk_average": 0.0
            }


# Singleton instance
db_service = DatabaseService()
