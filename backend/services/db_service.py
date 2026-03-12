"""
Database Service
MongoDB operations for logs, alerts, profiles, users, and nodes
"""

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from backend.config import (
    MONGODB_URI,
    DATABASE_NAME,
    HONEYPOT_LOGS_COLLECTION,
    AGENT_EVENTS_COLLECTION,
    ALERTS_COLLECTION,
    ATTACKER_PROFILES_COLLECTION,
    USERS_COLLECTION,
    NODES_COLLECTION,
    DECOYS_COLLECTION,
    NETWORK_EVENTS_COLLECTION,
    BLOCKED_IPS_COLLECTION,
    SECURITY_REPORTS_COLLECTION,
    ALERT_RISK_THRESHOLD,
    AUTH_ENABLED,
    DEMO_USER_ID
)
from backend.models.log_models import Alert, AttackerProfile, NetworkEvent, BlockedIP

logger = logging.getLogger(__name__)


class DatabaseService:
    """MongoDB database operations"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[Any] = None
    
    def _ensure_db(self) -> bool:
        """Check if database is connected. Returns True if connected."""
        if self.db is None:
            logger.warning("Database not connected - operation skipped (self.db is None)")
            return False
        logger.debug(f"Database check passed - db type: {type(self.db)}")
        return True
    
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
            self.db = None  # Ensure db is None on failure
            self.client = None
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    # ==================== USER OPERATIONS ====================
    
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        """Create new user"""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return None
            result = await self.db[USERS_COLLECTION].insert_one(user_data)
            logger.info(f"✓ User created: {user_data['email']}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            if self.db is None:
                return None
            user = await self.db[USERS_COLLECTION].find_one({"email": email})
            return user
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID — Express stores users with _id as ObjectId"""
        try:
            if self.db is None:
                return None
            from bson import ObjectId
            try:
                user = await self.db[USERS_COLLECTION].find_one({"_id": ObjectId(user_id)})
            except Exception:
                # Fallback: plain string id field (non-ObjectId stored IDs)
                user = await self.db[USERS_COLLECTION].find_one({"id": user_id})
            if user:
                user["_id"] = str(user["_id"])
            return user
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
            
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update existing user data"""
        try:
            if self.db is None:
                return False
            await self.db[USERS_COLLECTION].update_one(
                {"id": user_id},
                {"$set": update_data}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False
    
    # ==================== NODE OPERATIONS ====================
    
    async def create_node(self, node_data: Dict[str, Any]) -> Optional[str]:
        """Create new node"""
        try:
            if self.db is None:
                return None
            result = await self.db[NODES_COLLECTION].insert_one(node_data)
            logger.info(f"✓ Node created: {node_data['node_id']}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            return None
    
    async def get_nodes_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all nodes for a user"""
        try:
            if self.db is None:
                return []
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
            if self.db is None:
                return None
            node = await self.db[NODES_COLLECTION].find_one({"node_id": node_id})
            if node:
                node["_id"] = str(node["_id"])
            return node
        except Exception as e:
            logger.error(f"Error getting node: {e}")
            return None
    
    async def get_node_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get node by API key"""
        try:
            if self.db is None:
                return None
            node = await self.db[NODES_COLLECTION].find_one({"node_api_key": api_key})
            if node:
                node["_id"] = str(node["_id"])
            return node
        except Exception as e:
            logger.error(f"Error getting node by API key: {e}")
            return None
    
    async def update_node_status(self, node_id: str, status: str) -> bool:
        """Update node status"""
        try:
            if self.db is None:
                return False
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

    async def update_node(self, node_id: str, update_data: Dict[str, Any]) -> bool:
        """Update node with arbitrary fields"""
        if not self._ensure_db():
            return False
        try:
            await self.db[NODES_COLLECTION].update_one(
                {"node_id": node_id},
                {"$set": update_data}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating node: {e}")
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

    async def request_node_uninstall(self, node_id: str) -> bool:
        """Mark node for uninstall on next heartbeat"""
        if not self._ensure_db():
            return False
        try:
            await self.db[NODES_COLLECTION].update_one(
                {"node_id": node_id},
                {
                    "$set": {
                        "uninstall_requested": True,
                        "uninstall_requested_at": datetime.utcnow().isoformat(),
                        "status": "uninstall_requested"
                    }
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error requesting uninstall for node {node_id}: {e}")
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
        if not self._ensure_db():
            return []
        try:
            cursor = self.db[DECOYS_COLLECTION].find({"node_id": node_id})
            decoys = await cursor.to_list(length=1000)
            
            for decoy in decoys:
                decoy["_id"] = str(decoy["_id"])
            
            return decoys
        except Exception as e:
            logger.error(f"Error getting decoys: {e}")
            return []

    async def delete_decoys_by_node(self, node_id: str) -> bool:
        """Delete all decoys for a node"""
        if not self._ensure_db():
            return False
        try:
            await self.db[DECOYS_COLLECTION].delete_many({"node_id": node_id})
            return True
        except Exception as e:
            logger.error(f"Error deleting decoys for node {node_id}: {e}")
            return False

    async def delete_node_and_decoys(self, node_id: str) -> bool:
        """Delete node and all related decoys"""
        try:
            await self.delete_decoys_by_node(node_id)
            await self.delete_node(node_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting node and decoys for {node_id}: {e}")
            return False

    async def delete_all_node_data(self, node_id: str) -> bool:
        """Full cascade delete: node + decoys + alerts + events + logs"""
        if not self._ensure_db():
            return False
        try:
            collections = [
                DECOYS_COLLECTION,
                ALERTS_COLLECTION,
                AGENT_EVENTS_COLLECTION,
                HONEYPOT_LOGS_COLLECTION,
                NETWORK_EVENTS_COLLECTION,
            ]
            for col in collections:
                await self.db[col].delete_many({"node_id": node_id})
            await self.db[NODES_COLLECTION].delete_one({"node_id": node_id})
            logger.info(f"Full cascade delete completed for node {node_id}")
            return True
        except Exception as e:
            logger.error(f"Error in delete_all_node_data for {node_id}: {e}")
            return False
    
    async def save_deployed_decoy(self, decoy_data: Dict[str, Any]) -> Optional[str]:
        """Save a deployed decoy from agent (with file_path)"""
        if self.db is None:
            logger.error("save_deployed_decoy: self.db is None!")
            return None
        
        try:
            logger.info(f"save_deployed_decoy: Saving {decoy_data.get('file_name')} for node {decoy_data.get('node_id')}")
            
            # Remove triggers_count from data to avoid conflict with $setOnInsert
            data_to_set = {k: v for k, v in decoy_data.items() if k != 'triggers_count'}
            
            # Upsert based on node_id and file_path to avoid duplicates
            result = await self.db[DECOYS_COLLECTION].update_one(
                {
                    "node_id": decoy_data["node_id"], 
                    "file_path": decoy_data.get("file_path", decoy_data.get("file_name"))
                },
                {
                    "$set": data_to_set,
                    "$setOnInsert": {"triggers_count": 0}
                },
                upsert=True
            )
            
            # Return success for insert, update, or match
            if result.upserted_id:
                logger.info(f"✓ Inserted new decoy: {decoy_data.get('file_name')}")
                return str(result.upserted_id)
            elif result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"✓ Updated/matched decoy: {decoy_data.get('file_name')}")
                return decoy_data["node_id"]
            else:
                logger.warning(f"⚠️ No effect for decoy: {decoy_data.get('file_name')}")
                return decoy_data["node_id"]
                
        except Exception as e:
            logger.error(f"Error saving deployed decoy: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
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
        """Create high-risk alert and back-fill alert_id on the model"""
        try:
            alert_dict = alert.dict()
            result = await self.db[ALERTS_COLLECTION].insert_one(alert_dict)
            alert_id = str(result.inserted_id)

            # Store alert_id in the document so future lookups work
            await self.db[ALERTS_COLLECTION].update_one(
                {"_id": result.inserted_id},
                {"$set": {"alert_id": alert_id}}
            )

            # Mutate the Pydantic model so the caller (e.g. notification_service) sees the ID
            try:
                alert.alert_id = alert_id
            except Exception:
                pass

            logger.warning(f"🚨 ALERT CREATED: {alert.attack_type} from {alert.source_ip}")
            return alert_id
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None

    async def update_alert_status(self, alert_id: str, status: str) -> bool:
        """Update the status field of an alert (open / investigating / resolved)"""
        try:
            if self.db is None:
                return False
            from bson import ObjectId
            try:
                result = await self.db[ALERTS_COLLECTION].update_one(
                    {"_id": ObjectId(alert_id)},
                    {"$set": {"status": status}}
                )
            except Exception:
                result = await self.db[ALERTS_COLLECTION].update_one(
                    {"alert_id": alert_id},
                    {"$set": {"status": status}}
                )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating alert status: {e}")
            return False

    async def update_alert_notification(self, alert_id: str, notified: bool, notification_status: str) -> bool:
        """Update notification tracking fields on an alert"""
        try:
            if self.db is None:
                return False
            from bson import ObjectId
            try:
                result = await self.db[ALERTS_COLLECTION].update_one(
                    {"_id": ObjectId(alert_id)},
                    {"$set": {"notified": notified, "notification_status": notification_status}}
                )
            except Exception:
                result = await self.db[ALERTS_COLLECTION].update_one(
                    {"alert_id": alert_id},
                    {"$set": {"notified": notified, "notification_status": notification_status}}
                )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating alert notification: {e}")
            return False
    
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
    
    
    async def update_decoy_status(self, decoy_id: str, status: str) -> bool:
        """Update decoy status"""
        try:
            from bson import ObjectId
            result = await self.db[DECOYS_COLLECTION].update_one(
                {"_id": ObjectId(decoy_id)},
                {"$set": {"status": status}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating decoy status: {e}")
            return False
    
    async def delete_decoy(self, decoy_id: str) -> bool:
        """Delete decoy"""
        try:
            from bson import ObjectId
            result = await self.db[DECOYS_COLLECTION].delete_one({"_id": ObjectId(decoy_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting decoy: {e}")
            return False
    
    async def get_user_decoys(self, node_ids: List[str], limit: int = 50) -> List[Dict]:
        """Get all decoys for user's nodes"""
        try:
            cursor = self.db[DECOYS_COLLECTION].find({"node_id": {"$in": node_ids}}).limit(limit)
            decoys = await cursor.to_list(length=limit)
            
            for decoy in decoys:
                decoy["_id"] = str(decoy["_id"])
            
            return decoys
        except Exception as e:
            logger.error(f"Error getting user decoys: {e}")
            return []
    
    async def get_user_honeytokels(self, node_ids: List[str], limit: int = 50) -> List[Dict]:
        """Get all honeytokels (type='honeytoken') for user's nodes"""
        try:
            cursor = self.db[DECOYS_COLLECTION].find({
                "node_id": {"$in": node_ids},
                "type": "honeytoken"
            }).limit(limit)
            honeytokels = await cursor.to_list(length=limit)
            
            for token in honeytokels:
                token["_id"] = str(token["_id"])
            
            return honeytokels
        except Exception as e:
            logger.error(f"Error getting user honeytokels: {e}")
            return []
    
    async def get_node_honeytokels(self, node_id: str) -> List[Dict]:
        """Get all honeytokels for a node"""
        try:
            cursor = self.db[DECOYS_COLLECTION].find({
                "node_id": node_id,
                "type": "honeytoken"
            })
            honeytokels = await cursor.to_list(length=1000)
            
            for token in honeytokels:
                token["_id"] = str(token["_id"])
            
            return honeytokels
        except Exception as e:
            logger.error(f"Error getting node honeytokels: {e}")
            return []
    
    async def update_honeytoken_status(self, honeytoken_id: str, status: str) -> bool:
        """Update honeytoken status"""
        try:
            from bson import ObjectId
            result = await self.db[DECOYS_COLLECTION].update_one(
                {"_id": ObjectId(honeytoken_id)},
                {"$set": {"status": status}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating honeytoken status: {e}")
            return False
    
    async def delete_honeytoken(self, honeytoken_id: str) -> bool:
        """Delete honeytoken"""
        try:
            from bson import ObjectId
            result = await self.db[DECOYS_COLLECTION].delete_one({"_id": ObjectId(honeytoken_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting honeytoken: {e}")
            return False
    
    async def get_user_events(self, node_ids: List[str], limit: int = 100) -> List[Dict]:
        """Get all events (honeypot logs + agent events) for user's nodes"""
        try:
            # Get honeypot logs
            honeypot_cursor = self.db[HONEYPOT_LOGS_COLLECTION].find({
                "node_id": {"$in": node_ids}
            }).sort("timestamp", -1).limit(limit)
            honeypot_logs = await honeypot_cursor.to_list(length=limit)
            
            # Get agent events
            agent_cursor = self.db[AGENT_EVENTS_COLLECTION].find({
                "node_id": {"$in": node_ids}
            }).sort("timestamp", -1).limit(limit)
            agent_events = await agent_cursor.to_list(length=limit)
            
            # Combine and sort by timestamp
            all_events = honeypot_logs + agent_events
            all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            for event in all_events:
                event["_id"] = str(event["_id"])
            
            return all_events[:limit]
        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            return []
    
    async def get_node_events(self, node_id: str, limit: int = 100) -> List[Dict]:
        """Get all events for a specific node"""
        try:
            # Get honeypot logs
            honeypot_cursor = self.db[HONEYPOT_LOGS_COLLECTION].find({
                "node_id": node_id
            }).sort("timestamp", -1).limit(limit)
            honeypot_logs = await honeypot_cursor.to_list(length=limit)
            
            # Get agent events
            agent_cursor = self.db[AGENT_EVENTS_COLLECTION].find({
                "node_id": node_id
            }).sort("timestamp", -1).limit(limit)
            agent_events = await agent_cursor.to_list(length=limit)
            
            # Combine and sort
            all_events = honeypot_logs + agent_events
            all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            for event in all_events:
                event["_id"] = str(event["_id"])
            
            return all_events[:limit]
        except Exception as e:
            logger.error(f"Error getting node events: {e}")
            return []
    
    async def get_top_attacker_profiles(self, limit: int = 10) -> List[Dict]:
        """Get top attacker profiles by activity count"""
        try:
            cursor = self.db[ATTACKER_PROFILES_COLLECTION].find({}).sort("total_attacks", -1).limit(limit)
            profiles = await cursor.to_list(length=limit)
            
            for profile in profiles:
                profile["_id"] = str(profile["_id"])
            
            return profiles
        except Exception as e:
            logger.error(f"Error getting top attacker profiles: {e}")
            return []
    
    async def detect_scanner_bots(self, limit: int = 10) -> List[Dict]:
        """Detect scanner bots (high port_scan activity)"""
        try:
            # Find IPs with high port_scan activity
            cursor = self.db[ATTACKER_PROFILES_COLLECTION].find({
                "attack_types.port_scan": {"$exists": True, "$gt": 5}
            }).sort("total_attacks", -1).limit(limit)
            
            scanners = await cursor.to_list(length=limit)
            
            for scanner in scanners:
                scanner["_id"] = str(scanner["_id"])
            
            return scanners
        except Exception as e:
            logger.error(f"Error detecting scanner bots: {e}")
            return []
    
    async def update_node(self, node_id: str, updates: Dict[str, Any]) -> bool:
        """Update node with multiple fields"""
        try:
            result = await self.db[NODES_COLLECTION].update_one(
                {"node_id": node_id},
                {"$set": updates}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating node: {e}")
            return False
    
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


    # ==================== NETWORK EVENT OPERATIONS ====================

    async def save_network_event(self, event: NetworkEvent) -> Optional[str]:
        """Store a network connection event from the agent network monitor"""
        try:
            if self.db is None:
                return None
            doc = event.dict()
            result = await self.db[NETWORK_EVENTS_COLLECTION].insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error saving network event: {e}")
            return None

    async def get_recent_network_events(self, limit: int = 50, user_id: Optional[str] = None) -> List[Dict]:
        """Fetch recent network events, optionally scoped to a user"""
        try:
            if self.db is None:
                return []
            query: Dict[str, Any] = {}
            if AUTH_ENABLED and user_id:
                query = {"user_id": user_id}
            cursor = self.db[NETWORK_EVENTS_COLLECTION].find(query).sort("timestamp", -1).limit(limit)
            events = await cursor.to_list(length=limit)
            for e in events:
                e["_id"] = str(e["_id"])
            return events
        except Exception as e:
            logger.error(f"Error getting network events: {e}")
            return []

    # ==================== BLOCKED IP OPERATIONS ====================

    async def add_blocked_ip(self, block: BlockedIP) -> Optional[str]:
        """Queue an IP block request (status='pending')"""
        try:
            if self.db is None:
                return None
            doc = block.dict()
            result = await self.db[BLOCKED_IPS_COLLECTION].insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding blocked IP: {e}")
            return None

    async def get_pending_blocks(self, node_id: str) -> List[str]:
        """Return list of IP addresses pending a firewall block on this node"""
        try:
            if self.db is None:
                return []
            cursor = self.db[BLOCKED_IPS_COLLECTION].find(
                {"node_id": node_id, "status": "pending"}
            )
            docs = await cursor.to_list(length=100)
            return [d["ip_address"] for d in docs]
        except Exception as e:
            logger.error(f"Error getting pending blocks: {e}")
            return []

    async def confirm_block(self, node_id: str, ip_address: str) -> bool:
        """Mark an IP block as active once the agent confirms the firewall rule was added"""
        try:
            if self.db is None:
                return False
            result = await self.db[BLOCKED_IPS_COLLECTION].update_many(
                {"node_id": node_id, "ip_address": ip_address, "status": "pending"},
                {"$set": {"status": "active", "confirmed_at": datetime.utcnow().isoformat()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error confirming block: {e}")
            return False

    async def get_blocked_ips(self, user_id: Optional[str] = None) -> List[Dict]:
        """Return all blocked IPs, optionally scoped to a user's nodes"""
        try:
            if self.db is None:
                return []
            query: Dict[str, Any] = {}
            if AUTH_ENABLED and user_id:
                # Get user's node IDs first
                node_ids = [n["node_id"] for n in await self.get_nodes_by_user(user_id)]
                query = {"node_id": {"$in": node_ids}}
            cursor = self.db[BLOCKED_IPS_COLLECTION].find(query).sort("requested_at", -1)
            docs = await cursor.to_list(length=500)
            for d in docs:
                d["_id"] = str(d["_id"])
            return docs
        except Exception as e:
            logger.error(f"Error getting blocked IPs: {e}")
            return []


    # ==================== SECURITY REPORT OPERATIONS ====================

    async def save_report(self, report_data: dict) -> bool:
        """Upsert security report — one record per user_id (new replaces old)"""
        if not self._ensure_db():
            return False
        try:
            await self.db[SECURITY_REPORTS_COLLECTION].update_one(
                {"user_id": report_data["user_id"]},
                {"$set": report_data},
                upsert=True
            )
            logger.info(f"Security report saved for user {report_data['user_id']}")
            return True
        except Exception as e:
            logger.error(f"Error saving security report: {e}")
            return False

    async def get_report(self, user_id: str) -> Optional[dict]:
        """Get saved security report for user, or None if not generated yet"""
        if not self._ensure_db():
            return None
        try:
            report = await self.db[SECURITY_REPORTS_COLLECTION].find_one({"user_id": user_id})
            if report:
                report["_id"] = str(report["_id"])
            return report
        except Exception as e:
            logger.error(f"Error getting security report: {e}")
            return None

    async def get_alerts_by_user(self, user_id: str) -> List[Dict]:
        """Get all alerts for a user (for report aggregation)"""
        if not self._ensure_db():
            return []
        try:
            query = {"user_id": user_id} if AUTH_ENABLED else {}
            cursor = self.db[ALERTS_COLLECTION].find(query)
            alerts = await cursor.to_list(length=10000)
            for a in alerts:
                a["_id"] = str(a["_id"])
            return alerts
        except Exception as e:
            logger.error(f"Error getting alerts for user: {e}")
            return []

    async def get_recent_events_count(self, user_id: str, hours: int = 24) -> int:
        """Count honeypot + agent events in the last N hours for a user's nodes"""
        if not self._ensure_db():
            return 0
        try:
            from datetime import timedelta
            cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            nodes = await self.get_nodes_by_user(user_id)
            node_ids = [n["node_id"] for n in nodes]
            q = {"node_id": {"$in": node_ids}, "timestamp": {"$gte": cutoff}}
            h_count = await self.db[HONEYPOT_LOGS_COLLECTION].count_documents(q)
            a_count = await self.db[AGENT_EVENTS_COLLECTION].count_documents(q)
            return h_count + a_count
        except Exception as e:
            logger.error(f"Error counting recent events: {e}")
            return 0


# Singleton instance
db_service = DatabaseService()
