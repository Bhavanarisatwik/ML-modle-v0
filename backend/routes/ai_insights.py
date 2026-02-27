"""
AI Insights Routes
ML-powered threat analysis, attacker profiling, and scanner detection
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from backend.models.log_models import AttackerProfile
from backend.services.db_service import db_service
from backend.services.auth_service import auth_service
from backend.config import AUTH_ENABLED, DEMO_USER_ID

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
        source_ip = scanners[0].get("source_ip", "") if scanners else ""
        scanner_bots = [ScannerBot(str(s.get("source_ip", "")), int(s.get("total_attacks", 0)), str(s.get("last_seen", ""))).to_dict() for s in scanners]
        
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


# ─── Security Report Helpers ─────────────────────────────────────────────────

def _compute_health_score(
    total_nodes: int,
    online_nodes: int,
    open_alerts: int,
    critical_alerts: int,
    total_alerts: int,
) -> float:
    """
    Health score 0–10 (higher is healthier).
    Deductions: offline nodes (-3), open alerts (-4), critical alerts (-3).
    """
    score = 10.0
    if total_nodes > 0:
        score -= ((total_nodes - online_nodes) / total_nodes) * 3.0
    if total_alerts > 0:
        score -= (min(open_alerts / total_alerts, 1.0)) * 4.0
    elif open_alerts > 0:
        score -= min(open_alerts * 0.5, 4.0)
    if total_alerts > 0:
        score -= (min(critical_alerts / total_alerts, 1.0)) * 3.0
    return round(max(0.0, min(10.0, score)), 1)


def _generate_recommendations(
    health_score: float,
    online_nodes: int,
    total_nodes: int,
    critical_alerts: int,
    open_alerts: int,
    top_attack_types: list,
) -> list:
    """Return actionable recommendations based on current security posture."""
    recs = []
    if health_score < 4.0:
        recs.append("CRITICAL: Security posture is severely degraded. Immediately review all open alerts.")
    if total_nodes > 0 and online_nodes < total_nodes:
        offline = total_nodes - online_nodes
        recs.append(f"{offline} node(s) are offline. Verify agent connectivity and restart if needed.")
    if critical_alerts > 0:
        recs.append(f"Investigate {critical_alerts} critical alert(s) with risk score ≥ 8 immediately.")
    if open_alerts > 5:
        recs.append(f"You have {open_alerts} unresolved alerts. Triage and resolve or dismiss stale ones.")
    if top_attack_types:
        top_type = top_attack_types[0].get("type", "unknown")
        recs.append(f"Most common attack type is '{top_type}'. Deploy targeted decoys to increase attacker dwell time.")
    if not recs:
        recs.append("Security posture is healthy. Continue monitoring and keep agents up to date.")
    return recs


# ─── Report Endpoints ─────────────────────────────────────────────────────────

@router.post("/report")
async def generate_security_report(
    authorization: Optional[str] = Header(None)
):
    """
    Generate and save a security health report for the authenticated user.
    Aggregates: node health, alert counts, attack types, top attackers, recent events.
    One report per user — new report replaces the previous one in the DB.
    """
    try:
        user_id = get_user_id_from_header(authorization)

        # 1. Node stats
        nodes = await db_service.get_nodes_by_user(user_id)
        total_nodes = len(nodes)
        online_nodes = sum(1 for n in nodes if n.get("status") in ("active", "online"))

        # 2. Alert aggregation
        all_alerts = await db_service.get_alerts_by_user(user_id)
        total_alerts = len(all_alerts)
        open_alerts = sum(1 for a in all_alerts if a.get("status", "open") == "open")
        critical_alerts = sum(1 for a in all_alerts if (a.get("risk_score") or 0) >= 8)

        # 3. Attack type distribution
        attack_type_counts: Dict[str, int] = {}
        for alert in all_alerts:
            at = alert.get("attack_type") or alert.get("activity") or "unknown"
            attack_type_counts[at] = attack_type_counts.get(at, 0) + 1
        top_attack_types = sorted(
            [{"type": k, "count": v} for k, v in attack_type_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]

        # 4. Top attackers (from global attacker_profiles, filtered to this user's alert IPs)
        user_ips = {a.get("source_ip") for a in all_alerts if a.get("source_ip")}
        raw_profiles = await db_service.get_top_attacker_profiles(20)
        top_attackers = [
            {
                "ip": p.get("source_ip", ""),
                "risk_score": round(float(p.get("average_risk_score", 0)), 1),
                "attack_count": p.get("total_attacks", 0),
                "most_common_attack": p.get("most_common_attack", ""),
            }
            for p in raw_profiles
            if p.get("source_ip") in user_ips
        ][:5]

        # 5. Recent events count (last 24h)
        recent_events_count = await db_service.get_recent_events_count(user_id, hours=24)

        # 6. Health score + recommendations
        health_score = _compute_health_score(
            total_nodes, online_nodes, open_alerts, critical_alerts, total_alerts
        )
        recommendations = _generate_recommendations(
            health_score, online_nodes, total_nodes,
            critical_alerts, open_alerts, top_attack_types
        )

        # 7. Save (upsert) report
        report_data = {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat(),
            "health_score": health_score,
            "total_nodes": total_nodes,
            "online_nodes": online_nodes,
            "total_alerts": total_alerts,
            "open_alerts": open_alerts,
            "critical_alerts": critical_alerts,
            "top_attack_types": top_attack_types,
            "top_attackers": top_attackers,
            "recent_events_count": recent_events_count,
            "recommendations": recommendations,
        }
        await db_service.save_report(report_data)
        return report_data

    except Exception as e:
        logger.error(f"Error generating security report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_security_report(
    authorization: Optional[str] = Header(None)
):
    """
    Retrieve the last saved security report for the authenticated user.
    Returns { exists: false } if no report has been generated yet.
    """
    try:
        user_id = get_user_id_from_header(authorization)
        report = await db_service.get_report(user_id)
        return {"exists": bool(report), "report": report}
    except Exception as e:
        logger.error(f"Error getting security report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
