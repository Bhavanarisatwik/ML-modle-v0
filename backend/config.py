"""
Backend Configuration
MongoDB Atlas connection and service URLs
"""

import os
import logging

_logger = logging.getLogger(__name__)

# MongoDB Atlas Connection - Set via MONGODB_URI environment variable
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    # Fallback for local development only — NEVER commit real credentials
    MONGODB_URI = "mongodb+srv://decoyverse_user:XF07W87YU4JWVY8f@decoy.ygwnyen.mongodb.net/decoyvers?retryWrites=true&w=majority"
    _logger.warning(
        "⚠️  MONGODB_URI not set! Using hardcoded fallback. "
        "Set MONGODB_URI env var in production!"
    )

# Database name
DATABASE_NAME = "decoyvers"

# Collections
HONEYPOT_LOGS_COLLECTION = "honeypot_logs"
AGENT_EVENTS_COLLECTION = "agent_events"
ALERTS_COLLECTION = "alerts"
ATTACKER_PROFILES_COLLECTION = "attacker_profiles"
USERS_COLLECTION = "users"
NODES_COLLECTION = "nodes"
DECOYS_COLLECTION = "decoys"

# ML Service URL
ML_API_URL = os.getenv("ML_API_URL", "https://ml-modle-v0-2.onrender.com")
if ML_API_URL.rstrip("/").endswith("/predict"):
    ML_PREDICT_ENDPOINT = ML_API_URL
else:
    ML_PREDICT_ENDPOINT = f"{ML_API_URL}/predict"

# Alert threshold
ALERT_RISK_THRESHOLD = int(os.getenv("ALERT_RISK_THRESHOLD", "7"))

# Backend server config
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = int(os.getenv("PORT", 8001))

# CORS settings - Explicit origins required when using credentials
CORS_ORIGINS = [
    "https://decoy-verse-v2.vercel.app",      # Production frontend
    "https://decoyverse.vercel.app",           # Alternate production
    "http://localhost:5173",                   # Vite dev server
    "http://localhost:5174",                   # Vite dev server (alternate port)
    "http://localhost:3000",                   # React dev server
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
]

# API settings
API_TITLE = "Decoyvers Backend API"
API_VERSION = "2.0.0"
API_DESCRIPTION = "Multi-node cyber deception security platform"

# Authentication settings
# IMPORTANT: Must be True for production to enable user-scoped data
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "True").lower() == "true"

# JWT Secret Key - REQUIRED in production
# Check both JWT_SECRET_KEY (FastAPI standard) and JWT_SECRET (Express standard)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET")
if not JWT_SECRET_KEY:
    if AUTH_ENABLED:
        raise ValueError(
            "CRITICAL SECURITY ERROR: JWT_SECRET_KEY or JWT_SECRET environment variable must be set when AUTH_ENABLED=True. "
            "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    else:
        # Demo mode - use insecure default for testing only
        JWT_SECRET_KEY = "demo-secret-key-for-testing-only-DO-NOT-USE-IN-PRODUCTION"
        print("⚠️  WARNING: Using demo JWT secret. Set JWT_SECRET_KEY environment variable for production!")

JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Demo user (when AUTH_ENABLED = False)
DEMO_USER_ID = "demo-user"
DEMO_USER_EMAIL = "demo@decoyvers.local"

# ---------------------------------------------------------
# Notification Integrations
# ---------------------------------------------------------

# Slack Integration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Email Integration (SMTP)
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

# WhatsApp Integration (Twilio)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
ALERT_WHATSAPP_TO = os.getenv("ALERT_WHATSAPP_TO")
