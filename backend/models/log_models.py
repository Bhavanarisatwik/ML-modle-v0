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

class NotificationSettings(BaseModel):
    """Notification preferences for a user"""
    slackWebhook: Optional[str] = None
    emailAlertTo: Optional[str] = None
    whatsappNumber: Optional[str] = None

class UserProfileUpdate(BaseModel):
    """User profile update request"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    notifications: Optional[NotificationSettings] = None


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

class DeploymentConfig(BaseModel):
    """Initial deployment configuration for agent"""
    initial_decoys: int = Field(default=3, ge=0, le=20, description="Number of decoy files to deploy initially")
    initial_honeytokens: int = Field(default=5, ge=0, le=20, description="Number of honeytokens to deploy initially")
    deploy_path: Optional[str] = Field(default=None, description="Custom deployment directory path")


class NodeCreate(BaseModel):
    """Create new node request"""
    name: str = Field(..., min_length=1, max_length=100)
    os_type: Optional[str] = Field(default="windows", description="Operating system: windows, linux, macos")
    deployment_config: Optional[DeploymentConfig] = Field(default=None, description="Initial deployment settings")


class NodeResponse(BaseModel):
    """Node response"""
    node_id: str
    user_id: str
    name: str
    status: str  # "active" or "inactive"
    last_seen: Optional[str] = None
    created_at: str
    os_type: Optional[str] = "windows"
    ip_address: Optional[str] = None
    deployment_config: Optional[DeploymentConfig] = None


class NodeCreateResponse(NodeResponse):
    """Node creation response (includes API key once)"""
    node_api_key: str


class NodeUpdate(BaseModel):
    """Update node status"""
    status: str = Field(..., pattern="^(active|inactive)$")


# ==================== DECOY MODELS ====================

class DeployedDecoy(BaseModel):
    """Register a deployed decoy from agent"""
    file_name: str = Field(..., description="Name of the decoy file")
    file_path: str = Field(..., description="Full path where deployed on the node")
    type: str = Field(..., description="Type: file, service, port, honeytoken, aws_creds, db_creds, api_key")
    status: str = Field(default="active", description="Status: active, triggered, disabled")


class DecoyResponse(BaseModel):
    """Decoy file status"""
    id: Optional[str] = None
    node_id: str
    node_name: Optional[str] = None
    file_name: str
    file_path: Optional[str] = None
    type: str
    status: Optional[str] = "active"
    triggers_count: Optional[int] = 0
    last_accessed: Optional[str] = None
    created_at: Optional[str] = None


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
    # Process metadata (captured by file_monitor via psutil — optional)
    process_name: Optional[str] = Field(default=None, max_length=255, description="Process that accessed the file")
    pid: Optional[int] = Field(default=None, description="Process ID")
    process_user: Optional[str] = Field(default=None, max_length=100, description="OS user running the process")
    cmdline: Optional[str] = Field(default=None, max_length=500, description="Process command line")


class MLPrediction(BaseModel):
    """ML prediction result"""
    attack_type: str
    risk_score: int
    confidence: float
    is_anomaly: bool


class Alert(BaseModel):
    """High-risk alert"""

    class Config:
        allow_mutation = True

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
    status: Optional[str] = "open"
    notified: bool = False
    notification_status: Optional[str] = None


class NetworkEvent(BaseModel):
    """Network connection event from agent network monitor"""
    node_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: str
    source_ip: str
    dest_ip: str
    dest_port: int
    protocol: str = "TCP"
    status: str = "ESTABLISHED"
    process_name: Optional[str] = None
    rule_score: int = 0
    rule_triggers: List[str] = Field(default_factory=list)
    ml_attack_type: Optional[str] = None
    ml_risk_score: Optional[int] = None
    ml_confidence: Optional[float] = None


class BlockedIP(BaseModel):
    """IP block request and its status"""
    node_id: str
    ip_address: str
    requested_at: str
    requested_by_user_id: Optional[str] = None
    alert_id: Optional[str] = None
    status: str = "pending"  # pending | active | failed
    confirmed_at: Optional[str] = None


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


class SecurityReport(BaseModel):
    """Aggregated security health report — one per user, upserted on generate"""
    user_id: str
    generated_at: str                  # ISO datetime string
    health_score: float                # 0.0–10.0 (higher = healthier)
    total_nodes: int
    online_nodes: int
    total_alerts: int
    open_alerts: int
    critical_alerts: int               # alerts with risk_score >= 8
    top_attack_types: List[dict]       # [{"type": str, "count": int}]
    top_attackers: List[dict]          # [{"ip", "risk_score", "attack_count", "most_common_attack"}]
    recent_events_count: int           # events in last 24h
    recommendations: List[str]
    risk_score: Optional[int] = None
