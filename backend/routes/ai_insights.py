"""
AI Insights Routes
ML-powered threat analysis, attacker profiling, and scanner detection
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional, Dict, Any
import logging

from models.log_models import AttackerProfile
from services.db_service import db_service
from services.auth_service import auth_service
from config import AUTH_ENABLED, DEMO_USER_ID

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai-insights"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


class AttackerProfileResponse:
    """Attacker profile response model"""
    def __init__(self, doc):
        self.ip = doc.get("source_ip", "")
        self.threat_name = doc.get("most_common_attack", "Unknown")
        self.confidence = min(doc.get("average_risk_score", 0) / 100.0, 1.0)  # 0-1 scale
        self.ttps = self._get_mitre_tags(doc)
        self.description = self._generate_description(doc)
        self.activity_count = doc.get("total_attacks", 0)
        self.last_seen = doc.get("last_seen", "")

    @staticmethod
    def _get_mitre_tags(doc) -> List[str]:
        """Extract MITRE ATT&CK tags from attack types"""
        attack_types = doc.get("attack_types", {})
        mitre_mapping = {
            "brute_force": "T1110 - Brute Force",
            "sql_injection": "T1190 - Exploit Public-Facing Application",
            "exploit": "T1190 - Exploit Public-Facing Application",
            "port_scan": "T1046 - Network Service Discovery",
            "command_injection": "T1059 - Command and Scripting Interpreter",
            "path_traversal": "T1083 - File and Directory Discovery",
            "xss": "T1190 - Exploit Public-Facing Application",
            "privilege_escalation": "T1134 - Access Token Manipulation"
        }
        
        tags = []
        for attack_type in attack_types.keys():
            for key, tag in mitre_mapping.items():
                if key.lower() in attack_type.lower():
                    if tag not in tags:
                        tags.append(tag)
        
        return tags[:5]  # Return first 5 tags

    @staticmethod
    def _generate_description(doc) -> str:
        """Generate description from attack profile"""
        total = doc.get("total_attacks", 0)
        most_common = doc.get("most_common_attack", "Unknown")
        services = doc.get("services_targeted", {})
        
        service_list = ", ".join(list(services.keys())[:3]) if services else "multiple"
        
        return f"Attacker performing {most_common} attacks ({total} total) targeting {service_list}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip": self.ip,
            "threat_name": self.threat_name,
            "confidence": round(self.confidence, 2),
            "ttps": self.ttps,
            "description": self.description,
            "activity_count": self.activity_count,
            "last_seen": self.last_seen
        }


class ScannerBot:
    """Scanner bot detection"""
    def __init__(self, ip: str, activity_count: int, last_seen: str):
        self.ip = ip
        self.bot_type = self._classify_bot()
        self.confidence = min(activity_count / 10.0, 1.0)  # 0-1 scale
        self.activity_count = activity_count
        self.last_seen = last_seen

    def _classify_bot(self) -> str:
        """Classify bot type"""
        return "Port Scanner"  # Simplified for now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip": self.ip,
            "bot_type": self.bot_type,
            "confidence": round(self.confidence, 2),
            "activity_count": self.activity_count,
            "last_seen": self.last_seen
        }


@router.get("/insights")
async def get_ai_insights(
    limit: int = 10,
    authorization: Optional[str] = Header(None)
):
    """
    Get AI-powered security insights
    
    Returns:
    - attacker_profiles: Top threat actors
    - scanner_bots_detected: Detected scanning activity
    - confidence_score: Overall threat level
    - mitre_tags: Common attack techniques
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        # Get user's nodes
        nodes = await db_service.get_nodes_by_user(user_id)
        node_ids = [n.get("node_id") for n in nodes]
        
        if not node_ids:
            return {
                "attacker_profiles": [],
                "scanner_bots_detected": [],
                "confidence_score": 0.0,
                "mitre_tags": []
            }
        
        # Get top attacker profiles
        profiles = await db_service.get_top_attacker_profiles(limit)
        attacker_profiles = [AttackerProfileResponse(p).to_dict() for p in profiles]
        
        # Detect scanner bots (high port_scan activity)
        scanners = await db_service.detect_scanner_bots(limit)
        scanner_bots = [ScannerBot(s.get("source_ip"), s.get("total_attacks", 0), s.get("last_seen", "")).to_dict() for s in scanners]
        
        # Calculate overall confidence
        all_profiles = attacker_profiles + scanner_bots
        avg_confidence = sum([p.get("confidence", 0) for p in all_profiles]) / len(all_profiles) if all_profiles else 0.0
        
        # Extract MITRE tags
        all_ttps = set()
        for profile in attacker_profiles:
            for ttp in profile.get("ttps", []):
                all_ttps.add(ttp)
        
        return {
            "attacker_profiles": attacker_profiles,
            "scanner_bots_detected": scanner_bots,
            "confidence_score": round(avg_confidence, 2),
            "mitre_tags": list(all_ttps)[:10]
        }
    except Exception as e:
        logger.error(f"Error getting AI insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attacker-profile/{source_ip}")
async def get_attacker_profile(
    source_ip: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get detailed attacker profile for specific IP
    
    Returns: Threat analysis including attack history and MITRE mappings
    """
    try:
        # Get profile
        profile = await db_service.get_attacker_profile(source_ip)
        
        if not profile:
            return {
                "ip": source_ip,
                "threat_name": "Unknown",
                "confidence": 0.0,
                "ttps": [],
                "description": "No threat intelligence available",
                "activity_count": 0,
                "last_seen": None
            }
        
        return AttackerProfileResponse(profile).to_dict()
    except Exception as e:
        logger.error(f"Error getting attacker profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))
