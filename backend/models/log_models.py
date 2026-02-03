"""
Data Models for Logs, Alerts, Users, and Nodes
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr


# ==================== USER MODELS ====================

class UserCreate(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response (without password)"""
    id: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ==================== NODE MODELS ====================

class NodeCreate(BaseModel):
    """Create new node request"""
    name: str = Field(..., min_length=1, max_length=100)


class NodeResponse(BaseModel):
    """Node response"""
    node_id: str
    user_id: str
    name: str
    status: str  # "active" or "inactive"
    last_seen: Optional[str] = None
    created_at: str


class NodeCreateResponse(NodeResponse):
    """Node creation response (includes API key once)"""
    node_api_key: str


class NodeUpdate(BaseModel):
    """Update node status"""
    status: str = Field(..., pattern="^(active|inactive)$")


# ==================== DECOY MODELS ====================

class DecoyResponse(BaseModel):
    """Decoy file status"""
    node_id: str
    file_name: str
    type: str
    last_accessed: Optional[str] = None


# ==================== HONEYPOT & AGENT MODELS ====================

class HoneypotLog(BaseModel):
    """Honeypot activity log from SSH/FTP/Web services"""
    service: str = Field(..., max_length=50, description="Service type: SSH, FTP, WEB")
    source_ip: str = Field(..., max_length=45, description="Source IP address")
    activity: str = Field(..., max_length=100, description="Activity type: login_attempt, command, etc.")
    payload: str = Field(default="", max_length=10000, description="Payload data (max 10KB)")
    timestamp: str = Field(..., description="ISO timestamp")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    node_id: Optional[str] = Field(default=None, description="Deprecated: ignored. Use X-Node-Id header")


class AgentEvent(BaseModel):
    """Agent honeytoken access event"""
    timestamp: str = Field(..., description="ISO timestamp")
    hostname: str = Field(..., max_length=255, description="Hostname where event occurred")
    username: str = Field(..., max_length=100, description="Username who triggered event")
    file_accessed: str = Field(..., max_length=255, description="Honeytoken filename")
    file_path: str = Field(..., max_length=1024, description="Full file path")
    node_id: Optional[str] = Field(default=None, description="Deprecated: ignored. Use X-Node-Id header")
    action: str = Field(..., max_length=50, description="Action: ACCESSED, MODIFIED")
    severity: str = Field(..., max_length=20, description="Severity: CRITICAL, HIGH, MEDIUM, LOW")
    alert_type: str = Field(..., max_length=100, description="Alert type")


class MLPrediction(BaseModel):
    """ML prediction result"""
    attack_type: str
    risk_score: int
    confidence: float
    is_anomaly: bool


class Alert(BaseModel):
    """High-risk alert"""
    alert_id: Optional[str] = None
    timestamp: str
    source_ip: str
    service: str
    activity: str
    attack_type: str
    risk_score: int
    confidence: float
    payload: str = ""
    extra: Optional[Dict[str, Any]] = None
    node_id: Optional[str] = None
    user_id: Optional[str] = None


class AttackerProfile(BaseModel):
    """Attacker profiling data"""
    source_ip: str
    total_attacks: int = 0
    most_common_attack: str = "Normal"
    average_risk_score: float = 0.0
    first_seen: str
    last_seen: str
    attack_types: Dict[str, int] = Field(default_factory=dict)
    services_targeted: Dict[str, int] = Field(default_factory=dict)


class StatsResponse(BaseModel):
    """Dashboard statistics"""
    total_attacks: int
    active_alerts: int
    unique_attackers: int
    avg_risk_score: float
    high_risk_count: int
    total_nodes: Optional[int] = 0
    active_nodes: Optional[int] = 0
    recent_risk_average: Optional[float] = 0.0


class RecentAttack(BaseModel):
    """Recent attack entry"""
    timestamp: str
    source_ip: str
    service: str
    activity: str
    attack_type: Optional[str] = None
    risk_score: Optional[int] = None
