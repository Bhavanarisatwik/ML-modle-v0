"""
Decoyvers Backend API
FastAPI server for multi-node cyber deception platform
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys

from config import (
    API_TITLE, API_VERSION, API_DESCRIPTION, CORS_ORIGINS,
    AUTH_ENABLED, BACKEND_HOST, BACKEND_PORT
)
from routes import auth_router, nodes_router, honeypot_router, agent_router, alerts_router
from services.db_service import db_service
from services.db_indexes import create_indexes

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
                "GET /nodes/{id}/decoys - Get node decoys"
            ]
        },
        "log_ingestion": {
            "endpoints": [
                "POST /api/honeypot-log - Honeypot logs",
                "POST /api/agent-alert - Agent events"
            ]
        },
        "dashboard": {
            "endpoints": [
                "GET /api/stats - Dashboard stats",
                "GET /api/recent-attacks - Recent attacks",
                "GET /api/alerts - All alerts",
                "GET /api/attacker-profile/{ip} - Attacker profile",
                "GET /api/health - Health check"
            ]
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return {
        "status": "error",
        "code": exc.status_code,
        "detail": exc.detail
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=False
    )
