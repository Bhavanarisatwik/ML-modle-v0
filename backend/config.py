"""
Backend Configuration
MongoDB Atlas connection and service URLs
"""

import os

# MongoDB Atlas Connection
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://satwikbhavanari_db_user:<db_password>@decoyverseprod.wogbyey.mongodb.net/?appName=DecoyVerseprod"
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
ML_API_URL = os.getenv("ML_API_URL", "http://localhost:8000")
if ML_API_URL.rstrip("/").endswith("/predict"):
    ML_PREDICT_ENDPOINT = ML_API_URL
else:
    ML_PREDICT_ENDPOINT = f"{ML_API_URL}/predict"

# Alert threshold
ALERT_RISK_THRESHOLD = 7

# Backend server config
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = int(os.getenv("PORT", 8001))

# CORS settings
CORS_ORIGINS = ["*"]  # Allow all origins for demo

# API settings
API_TITLE = "Decoyvers Backend API"
API_VERSION = "2.0.0"
API_DESCRIPTION = "Multi-node cyber deception security platform"

# Authentication settings
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "True").lower() == "true"

# JWT Secret Key - REQUIRED in production
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    if AUTH_ENABLED:
        raise ValueError(
            "CRITICAL SECURITY ERROR: JWT_SECRET_KEY environment variable must be set when AUTH_ENABLED=True. "
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
