"""
Decoyvers Backend API
FastAPI server for multi-node cyber deception platform
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import (
    API_TITLE, API_VERSION, API_DESCRIPTION, CORS_ORIGINS,
    AUTH_ENABLED, BACKEND_HOST, BACKEND_PORT
)
from backend.routes import auth_router, nodes_router, honeypot_router, agent_router, alerts_router, decoys_router, honeytokels_router, logs_router, ai_insights_router, install_router
from backend.services.db_service import db_service
from backend.services.db_indexes import create_indexes

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""
    # Startup
    logger.info("🚀 Backend server starting...")
    await db_service.connect()
    if db_service.db is not None:
        await create_indexes(db_service.db)
        logger.info("✓ Database indexes created")
    logger.info(f"🔐 Authentication: {'ENABLED' if AUTH_ENABLED else 'DISABLED (Demo Mode)'}")
    yield
    # Shutdown
    logger.info("🛑 Backend server shutting down...")
    await db_service.disconnect()


# Create FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(nodes_router)
app.include_router(honeypot_router)
app.include_router(agent_router)
app.include_router(alerts_router)
app.include_router(decoys_router)
app.include_router(honeytokels_router)
app.include_router(logs_router)
app.include_router(ai_insights_router)
app.include_router(install_router)


# Root endpoint
@app.get("/")
async def root():
    """Service information"""
    return {
        "name": "Decoyvers Backend API",
        "version": "2.0.0",
        "description": "Multi-node cyber deception security platform",
        "authentication": {
            "enabled": AUTH_ENABLED,
            "mode": "production" if AUTH_ENABLED else "demo",
            "endpoints": [
                "POST /auth/register - Register new user",
                "POST /auth/login - Login user"
            ]
        },
        "node_management": {
            "endpoints": [
                "POST /nodes - Create node",
                "GET /nodes - List nodes",
                "PATCH /nodes/{id} - Update node status",
                "DELETE /nodes/{id} - Delete node",
                "GET /agent/download/{node_id} - Download agent config"
            ]
        },
        "alerts": {
            "endpoints": [
                "GET /api/alerts - Get alerts (with severity/status filters)",
                "PATCH /api/alerts/{id} - Update alert status"
            ]
        },
        "decoys": {
            "endpoints": [
                "GET /api/decoys - Get all decoys",
                "GET /api/decoys/node/{node_id} - Get node decoys",
                "PATCH /api/decoys/{id} - Update decoy status",
                "DELETE /api/decoys/{id} - Delete decoy"
            ]
        },
        "honeytokels": {
            "endpoints": [
                "GET /api/honeytokels - Get all honeytokels",
                "GET /api/honeytokels/node/{node_id} - Get node honeytokels",
                "PATCH /api/honeytokels/{id} - Update honeytoken status",
                "DELETE /api/honeytokels/{id} - Delete honeytoken"
            ]
        },
        "logs": {
            "endpoints": [
                "GET /api/logs - Get event logs (with node_id/severity/search filters)",
                "GET /api/logs/node/{node_id} - Get node logs"
            ]
        },
        "ai_insights": {
            "endpoints": [
                "GET /api/ai/insights - Get AI threat analysis",
                "GET /api/ai/attacker-profile/{ip} - Get attacker profile"
            ]
        },
        "agent": {
            "endpoints": [
                "POST /api/agent-alert - Submit agent alert (node auth required)",
                "POST /api/agent/register - Register agent",
                "POST /api/agent/heartbeat - Agent heartbeat",
                "GET /api/agent/download/{node_id} - Download agent package"
            ]
        },
        "log_ingestion": {
            "endpoints": [
                "POST /api/honeypot-log - Honeypot logs (node auth required)",
                "POST /api/agent-alert - Agent events (node auth required)"
            ]
        },
        "dashboard": {
            "endpoints": [
                "GET /api/stats - Dashboard stats",
                "GET /api/recent-attacks - Recent attacks",
                "GET /api/health - Health check"
            ]
        }
    }


from fastapi.responses import JSONResponse

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "detail": exc.detail
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=False
    )
