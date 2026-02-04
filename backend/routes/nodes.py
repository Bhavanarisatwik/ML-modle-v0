"""
Node Management Routes
CRUD operations for nodes
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse, StreamingResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime
import logging
import json
import io
from pathlib import Path

from backend.models.log_models import NodeCreate, NodeResponse, NodeCreateResponse, NodeUpdate, DecoyResponse
from backend.services.db_service import db_service
from backend.services.node_service import node_service
from backend.config import AUTH_ENABLED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nodes", tags=["nodes"])


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user_id from Authorization header - returns None if auth fails"""
    from backend.services.auth_service import auth_service
    from backend.config import DEMO_USER_ID, AUTH_ENABLED
    
    user_id = auth_service.extract_user_from_token(authorization)
    
    # Only use DEMO_USER_ID if AUTH is disabled
    if not user_id and not AUTH_ENABLED:
        return DEMO_USER_ID
    
    return user_id


@router.post("", response_model=NodeCreateResponse)
async def create_node(
    node: NodeCreate,
    authorization: Optional[str] = Header(None)
):
    """
    Create new node
    
    Returns node_id and node_api_key for authentication
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Create node with deployment config
        deployment_config = None
        if node.deployment_config:
            deployment_config = node.deployment_config.model_dump()
        
        node_data = node_service.create_node_data(
            user_id, 
            node.name,
            node.os_type or "windows",
            deployment_config
        )
        result = await db_service.create_node(node_data)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create node")
        
        return NodeCreateResponse(**node_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[NodeResponse])
async def list_nodes(authorization: Optional[str] = Header(None)):
    """
    List all nodes for authenticated user

    Returns user-scoped node list
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get nodes for user
        nodes = await db_service.get_nodes_by_user(user_id)
        
        return [NodeResponse(**node) for node in nodes]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.patch("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: str,
    update: NodeUpdate,
    authorization: Optional[str] = Header(None)
):
    """
    Update node status
    
    Validates ownership before updating
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Update status
        await db_service.update_node_status(node_id, update.status)
        
        # Get updated node
        updated_node = await db_service.get_node_by_id(node_id)
        
        return NodeResponse(**updated_node)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{node_id}")
async def delete_node(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Delete node
    
    Validates ownership before deleting
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Delete node
        await db_service.delete_node(node_id)
        
        return {"status": "success", "message": f"Node {node_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{node_id}/decoys", response_model=List[DecoyResponse])
async def get_node_decoys(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Get all decoy files for a node
    
    Returns list of honeytoken files with access timestamps
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Get decoys
        decoys = await db_service.get_decoys_by_node(node_id)
        
        return [DecoyResponse(**decoy) for decoy in decoys]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting decoys: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{node_id}/agent-download")
async def download_agent(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Download Windows batch installer for the agent
    
    Returns a batch file (.bat) that:
    1. Bypasses PowerShell execution policy
    2. Creates C:\DecoyVerse directory
    3. Downloads agent files from GitHub
    4. Writes agent_config.json with credentials
    5. Installs Python and dependencies
    6. Runs the agent
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get node
        node = await db_service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Verify ownership
        if AUTH_ENABLED and node["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Get deployment config with defaults
        deployment_config = node.get("deployment_config", {
            "initial_decoys": 3,
            "initial_honeytokens": 5,
            "deploy_path": None
        })
        
        # Create config JSON - escape for batch file
        config = {
            "node_id": node["node_id"],
            "node_api_key": node["node_api_key"],
            "node_name": node["name"],
            "os_type": node.get("os_type", "windows"),
            "backend_url": "https://ml-modle-v0-1.onrender.com/api",
            "ml_service_url": "https://ml-modle-v0-2.onrender.com",
            "deployment_config": deployment_config
        }
        config_json = json.dumps(config, indent=2)
        
        # Generate batch installer script
        bat_script = f'''@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title DecoyVerse Agent Installer
color 0B

echo.
echo ===============================================
echo   DecoyVerse Agent Installer v2.0
echo   Node: {node["name"]}
echo ===============================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] ERROR: Administrator privileges required!
    echo.
    echo     Please right-click this file and select
    echo     "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo [OK] Running with Administrator privileges
echo.

set "INSTALL_DIR=C:\\DecoyVerse"
set "GITHUB_REPO=https://raw.githubusercontent.com/Bhavanarisatwik/ML-modle-v0/main"

echo [1/6] Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"

echo [2/6] Checking Python installation...
set "PYTHON_CMD="

:: Check common Python locations
where python >nul 2>&1 && (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do (
        echo %%i | findstr /C:"Python 3" >nul && set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
    if exist "C:\\Python311\\python.exe" set "PYTHON_CMD=C:\\Python311\\python.exe"
)

if not defined PYTHON_CMD (
    if exist "%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\\Programs\\Python\\Python311\\python.exe"
)

if not defined PYTHON_CMD (
    if exist "%LOCALAPPDATA%\\Programs\\Python\\Python310\\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\\Programs\\Python\\Python310\\python.exe"
)

if not defined PYTHON_CMD (
    echo   Python not found. Installing Python 3.11...
    echo   Downloading Python installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%INSTALL_DIR%\\python-installer.exe'"
    
    echo   Installing Python (this may take a minute)...
    "%INSTALL_DIR%\\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
    del "%INSTALL_DIR%\\python-installer.exe"
    
    :: Refresh PATH
    set "PATH=%PATH%;C:\\Program Files\\Python311;C:\\Program Files\\Python311\\Scripts"
    set "PYTHON_CMD=python"
    echo   Python installed successfully!
) else (
    echo   Found Python: %PYTHON_CMD%
)

echo [3/6] Writing agent configuration...
(
echo {{
echo   "node_id": "{node["node_id"]}",
echo   "node_api_key": "{node["node_api_key"]}",
echo   "node_name": "{node["name"]}",
echo   "os_type": "{node.get("os_type", "windows")}",
echo   "backend_url": "https://ml-modle-v0-1.onrender.com/api",
echo   "ml_service_url": "https://ml-modle-v0-2.onrender.com",
echo   "deployment_config": {{
echo     "initial_decoys": {deployment_config.get("initial_decoys", 3)},
echo     "initial_honeytokens": {deployment_config.get("initial_honeytokens", 5)},
echo     "deploy_path": null
echo   }}
echo }}
) > "%INSTALL_DIR%\\agent_config.json"
echo   Config saved!

echo [4/6] Downloading agent files...
powershell -Command "Invoke-WebRequest -Uri '%GITHUB_REPO%/agent.py' -OutFile '%INSTALL_DIR%\\agent.py' -UseBasicParsing" 2>nul && echo   Downloaded: agent.py
powershell -Command "Invoke-WebRequest -Uri '%GITHUB_REPO%/agent_setup.py' -OutFile '%INSTALL_DIR%\\agent_setup.py' -UseBasicParsing" 2>nul && echo   Downloaded: agent_setup.py
powershell -Command "Invoke-WebRequest -Uri '%GITHUB_REPO%/agent_config.py' -OutFile '%INSTALL_DIR%\\agent_config.py' -UseBasicParsing" 2>nul && echo   Downloaded: agent_config.py
powershell -Command "Invoke-WebRequest -Uri '%GITHUB_REPO%/file_monitor.py' -OutFile '%INSTALL_DIR%\\file_monitor.py' -UseBasicParsing" 2>nul && echo   Downloaded: file_monitor.py
powershell -Command "Invoke-WebRequest -Uri '%GITHUB_REPO%/alert_sender.py' -OutFile '%INSTALL_DIR%\\alert_sender.py' -UseBasicParsing" 2>nul && echo   Downloaded: alert_sender.py

echo [5/6] Installing Python dependencies...
%PYTHON_CMD% -m pip install --quiet --upgrade pip 2>nul
%PYTHON_CMD% -m pip install --quiet requests watchdog psutil 2>nul
echo   Dependencies installed!

echo.
echo [6/6] Starting DecoyVerse agent...
echo ===============================================
echo.

cd /d "%INSTALL_DIR%"
%PYTHON_CMD% agent.py

echo.
echo ===============================================
echo   If the agent exited, you can restart it with:
echo   cd %INSTALL_DIR%
echo   %PYTHON_CMD% agent.py
echo ===============================================
echo.
pause
'''
        
        # Return batch script
        return StreamingResponse(
            io.BytesIO(bat_script.encode('utf-8')),
            media_type="application/x-bat",
            headers={
                "Content-Disposition": f"attachment; filename=DecoyVerse-Setup-{node['name'].replace(' ', '_')}.bat"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_node_stats(authorization: Optional[str] = Header(None)):
    """
    Get node statistics (total, online, offline)
    
    Returns aggregated node status for user
    """
    try:
        user_id = get_user_id_from_header(authorization)
        
        if not user_id and AUTH_ENABLED:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get all user nodes
        nodes = await db_service.get_nodes_by_user(user_id)
        
        total = len(nodes)
        online = sum(1 for node in nodes if node.get("status") == "online")
        offline = total - online
        
        return {
            "total": total,
            "online": online,
            "offline": offline
        }
    except Exception as e:
        logger.error(f"Error getting node stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
