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
        
        # Generate PowerShell installer script (more reliable than batch)
        ps_script = f'''
# DecoyVerse Agent Installer v2.0
# Node: {node["name"]}

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "DecoyVerse Agent Installer"

function Write-Step($step, $msg) {{
    Write-Host "[$step] " -NoNewline -ForegroundColor Cyan
    Write-Host $msg
}}

function Write-Success($msg) {{
    Write-Host "  [OK] " -NoNewline -ForegroundColor Green
    Write-Host $msg
}}

function Write-Fail($msg) {{
    Write-Host "  [X] " -NoNewline -ForegroundColor Red
    Write-Host $msg
}}

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {{
    Write-Host ""
    Write-Host "===============================================" -ForegroundColor Cyan
    Write-Host "  DecoyVerse Agent Installer v2.0" -ForegroundColor White
    Write-Host "  Node: {node["name"]}" -ForegroundColor Yellow
    Write-Host "===============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[!] Requesting Administrator privileges..." -ForegroundColor Yellow
    Write-Host "    Please click Yes on the UAC prompt..." -ForegroundColor Gray
    Write-Host ""
    
    # Re-launch as admin
    $scriptPath = $MyInvocation.MyCommand.Path
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" -Verb RunAs -Wait
    exit
}}

Clear-Host
Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  DecoyVerse Agent Installer v2.0" -ForegroundColor White
Write-Host "  Node: {node["name"]}" -ForegroundColor Yellow
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[OK] Running with Administrator privileges" -ForegroundColor Green
Write-Host ""

$INSTALL_DIR = "C:\\DecoyVerse"
$GITHUB_REPO = "https://raw.githubusercontent.com/Bhavanarisatwik/ML-modle-v0/main"

# Step 1: Create directory
Write-Step "1/6" "Creating installation directory..."
if (-not (Test-Path $INSTALL_DIR)) {{
    New-Item -ItemType Directory -Path $INSTALL_DIR -Force | Out-Null
}}
Set-Location $INSTALL_DIR
Write-Success "Directory ready: $INSTALL_DIR"

# Step 2: Check Python
Write-Step "2/6" "Checking Python installation..."
$pythonCmd = $null

# Try to find Python
try {{
    $pythonVersion = & python --version 2>&1
    if ($pythonVersion -match "Python 3") {{
        $pythonCmd = "python"
    }}
}} catch {{}}

if (-not $pythonCmd) {{
    try {{
        $pythonVersion = & python3 --version 2>&1
        if ($pythonVersion -match "Python 3") {{
            $pythonCmd = "python3"
        }}
    }} catch {{}}
}}

if (-not $pythonCmd) {{
    $paths = @(
        "$env:LOCALAPPDATA\\Programs\\Python\\Python311\\python.exe",
        "$env:LOCALAPPDATA\\Programs\\Python\\Python310\\python.exe",
        "C:\\Python311\\python.exe",
        "C:\\Python310\\python.exe"
    )
    foreach ($p in $paths) {{
        if (Test-Path $p) {{
            $pythonCmd = $p
            break
        }}
    }}
}}

if (-not $pythonCmd) {{
    Write-Fail "Python not found. Please install Python 3.10+ from python.org"
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}}
Write-Success "Found Python: $pythonCmd"

# Step 3: Write config
Write-Step "3/6" "Writing agent configuration..."
$config = @'
{{
  "node_id": "{node["node_id"]}",
  "node_api_key": "{node["node_api_key"]}",
  "node_name": "{node["name"]}",
  "os_type": "{node.get("os_type", "windows")}",
  "backend_url": "https://ml-modle-v0-1.onrender.com/api",
  "ml_service_url": "https://ml-modle-v0-2.onrender.com",
  "deployment_config": {{
    "initial_decoys": {deployment_config.get("initial_decoys", 3)},
    "initial_honeytokens": {deployment_config.get("initial_honeytokens", 5)},
    "deploy_path": null
  }}
}}
'@
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText("$INSTALL_DIR\\agent_config.json", $config, $utf8NoBom)
Write-Success "Config saved!"

# Step 4: Download agent files
Write-Step "4/6" "Downloading agent files..."
$files = @("agent.py", "agent_setup.py", "agent_config.py", "file_monitor.py", "alert_sender.py")
foreach ($file in $files) {{
    try {{
        Invoke-WebRequest -Uri "$GITHUB_REPO/$file" -OutFile "$INSTALL_DIR\\$file" -UseBasicParsing
        Write-Success "Downloaded: $file"
    }} catch {{
        Write-Fail "Failed to download: $file"
    }}
}}

# Step 5: Install dependencies
Write-Step "5/6" "Installing Python dependencies..."
& $pythonCmd -m pip install --quiet --upgrade pip 2>$null
& $pythonCmd -m pip install --quiet requests watchdog psutil 2>$null
Write-Success "Dependencies installed!"

# Step 6: Run agent
Write-Host ""
Write-Step "6/6" "Starting DecoyVerse agent..."
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $INSTALL_DIR
& $pythonCmd agent.py

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Agent stopped. To restart manually:" -ForegroundColor White
Write-Host "  cd $INSTALL_DIR" -ForegroundColor Gray
Write-Host "  python agent.py" -ForegroundColor Gray
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
'''
        
        # Return PowerShell script
        return StreamingResponse(
            io.BytesIO(ps_script.encode('utf-8')),
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
