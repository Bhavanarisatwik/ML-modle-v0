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


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract user_id from Authorization header"""
    from backend.services.auth_service import auth_service
    from backend.config import DEMO_USER_ID
    
    user_id = auth_service.extract_user_from_token(authorization)
    return user_id or DEMO_USER_ID


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
    Download Windows PowerShell installer for the agent
    
    Returns a PowerShell script (.ps1) that:
    1. Creates C:\DecoyVerse directory
    2. Downloads agent files from GitHub
    3. Writes agent_config.json with credentials
    4. Installs Python and dependencies
    5. Deploys honeytokens/decoys
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
        
        # Create config JSON
        config = {
            "node_id": node["node_id"],
            "node_api_key": node["node_api_key"],
            "node_name": node["name"],
            "os_type": node.get("os_type", "windows"),
            "backend_url": "https://ml-modle-v0-1.onrender.com/api",
            "ml_service_url": "https://ml-modle-v0-2.onrender.com",
            "deployment_config": deployment_config
        }
        config_json = json.dumps(config, indent=2).replace("'", "''")  # Escape for PS
        
        # Generate PowerShell installer script
        ps_script = f'''#Requires -RunAsAdministrator
# ===============================================
# DecoyVerse Agent Installer
# Node: {node["name"]}
# Node ID: {node["node_id"]}
# Generated: {datetime.now().isoformat()}
# ===============================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  DecoyVerse Agent Installer v2.0" -ForegroundColor Cyan
Write-Host "  Node: {node["name"]}" -ForegroundColor Yellow
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$InstallDir = "C:\\DecoyVerse"
$GitHubRepo = "https://raw.githubusercontent.com/satwikShresth/ML-modle-v0/main"
$AgentFiles = @("agent.py", "agent_setup.py", "agent_config.py")

# Step 1: Create installation directory
Write-Host "[1/6] Creating installation directory..." -ForegroundColor Green
if (!(Test-Path $InstallDir)) {{
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}}
Set-Location $InstallDir

# Step 2: Check Python installation
Write-Host "[2/6] Checking Python installation..." -ForegroundColor Green
$pythonCmd = $null
$pythonPaths = @(
    "python",
    "python3",
    "C:\\Python311\\python.exe",
    "C:\\Python310\\python.exe",
    "C:\\Python39\\python.exe",
    "$env:LOCALAPPDATA\\Programs\\Python\\Python311\\python.exe",
    "$env:LOCALAPPDATA\\Programs\\Python\\Python310\\python.exe"
)

foreach ($path in $pythonPaths) {{
    try {{
        $version = & $path --version 2>&1
        if ($version -match "Python 3") {{
            $pythonCmd = $path
            Write-Host "  Found Python: $version" -ForegroundColor Gray
            break
        }}
    }} catch {{ }}
}}

if (!$pythonCmd) {{
    Write-Host "  Python not found. Installing Python 3.11..." -ForegroundColor Yellow
    
    # Download Python installer
    $pythonInstaller = "$InstallDir\\python-installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $pythonInstaller
    
    # Install Python silently
    Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_pip=1"
    Remove-Item $pythonInstaller -Force
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $pythonCmd = "python"
    Write-Host "  Python installed successfully" -ForegroundColor Green
}}

# Step 3: Write agent configuration
Write-Host "[3/6] Writing agent configuration..." -ForegroundColor Green
$configContent = @'
{config_json}
'@
[System.IO.File]::WriteAllText("$InstallDir\\agent_config.json", $configContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "  Config saved to $InstallDir\\agent_config.json" -ForegroundColor Gray

# Step 4: Download agent files from GitHub
Write-Host "[4/6] Downloading agent files..." -ForegroundColor Green
foreach ($file in $AgentFiles) {{
    $url = "$GitHubRepo/$file"
    $dest = "$InstallDir\\$file"
    try {{
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
        Write-Host "  Downloaded: $file" -ForegroundColor Gray
    }} catch {{
        Write-Host "  Warning: Failed to download $file - $_" -ForegroundColor Yellow
    }}
}}

# Step 5: Install Python dependencies
Write-Host "[5/6] Installing Python dependencies..." -ForegroundColor Green
try {{
    & $pythonCmd -m pip install --quiet --upgrade pip 2>$null
    & $pythonCmd -m pip install --quiet requests watchdog psutil 2>$null
    Write-Host "  Dependencies installed" -ForegroundColor Gray
}} catch {{
    Write-Host "  Warning: Some dependencies may not have installed" -ForegroundColor Yellow
}}

# Step 6: Run the agent
Write-Host "[6/6] Starting DecoyVerse agent..." -ForegroundColor Green
Write-Host ""

try {{
    # Change to install directory and run agent
    Set-Location $InstallDir
    & $pythonCmd agent.py
}} catch {{
    Write-Host "Error running agent: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual start command:" -ForegroundColor Yellow
    Write-Host "  cd $InstallDir" -ForegroundColor White
    Write-Host "  $pythonCmd agent.py" -ForegroundColor White
}}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "  Agent installed at: $InstallDir" -ForegroundColor Gray
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
'''
        
        # Return PowerShell script
        return StreamingResponse(
            io.BytesIO(ps_script.encode('utf-8-sig')),  # BOM for Windows PowerShell
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=DecoyVerse-Setup-{node['name'].replace(' ', '_')}.ps1"
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
