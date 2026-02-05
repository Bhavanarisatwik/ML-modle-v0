"""
Installer Routes - Serve agent installation scripts and generate pre-configured installers
"""

from fastapi import APIRouter, Response, HTTPException, Header
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import Optional
import io
import json
import zipfile
import logging

from backend.services.db_service import db_service
from backend.config import AUTH_ENABLED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/install", tags=["install"])

INSTALLERS_DIR = Path(__file__).parent.parent / "installers"


def get_user_id_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user_id from Authorization header"""
    from backend.services.auth_service import auth_service
    from backend.config import DEMO_USER_ID
    
    user_id = auth_service.extract_user_from_token(authorization)
    
    if not user_id and not AUTH_ENABLED:
        return DEMO_USER_ID
    
    return user_id


@router.get("/windows")
async def get_windows_installer():
    """Download Windows PowerShell installer script"""
    script_path = INSTALLERS_DIR / "install_windows.ps1"
    
    if not script_path.exists():
        return Response(
            content="# Installer not found",
            media_type="text/plain",
            status_code=404
        )
    
    content = script_path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=install_decoyverse.ps1"
        }
    )


@router.get("/linux")
async def get_linux_installer():
    """Download Linux bash installer script"""
    script_path = INSTALLERS_DIR / "install_linux.sh"
    
    if not script_path.exists():
        return Response(
            content="# Installer not found",
            media_type="text/plain",
            status_code=404
        )
    
    content = script_path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=install_decoyverse.sh"
        }
    )


@router.get("/macos")
async def get_macos_installer():
    """Download macOS bash installer script"""
    script_path = INSTALLERS_DIR / "install_macos.sh"
    
    if not script_path.exists():
        return Response(
            content="# Installer not found",
            media_type="text/plain",
            status_code=404
        )
    
    content = script_path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=install_decoyverse.sh"
        }
    )


@router.post("/generate-installer/{node_id}")
async def generate_installer(
    node_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Generate a pre-configured installer for a specific node
    
    Creates a ZIP containing:
    - Pre-configured agent_config.json with node credentials
    - PowerShell installation script
    - Setup instructions
    
    Returns: ZIP file download
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
        if AUTH_ENABLED and node.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Create agent configuration
        agent_config = {
            "node_id": node["node_id"],
            "node_api_key": node["node_api_key"],
            "node_name": node["name"],
            "os_type": node.get("os_type", "windows"),
            "backend_url": "https://ml-modle-v0-1.onrender.com/api",
            "ml_service_url": "https://ml-modle-v0-2.onrender.com",
            "deployment_config": node.get("deployment_config", {
                "initial_decoys": 3,
                "initial_honeytokens": 5,
                "deploy_path": None
            })
        }
        
        # Create in-memory ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            
            # Add agent config
            zip_file.writestr(
                "agent_config.json",
                json.dumps(agent_config, indent=2)
            )
            
            # Add installation script (PowerShell)
            install_script = f"""# DecoyVerse Agent Auto-Installer
# Pre-configured for node: {node['name']}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  DecoyVerse Agent Installer" -ForegroundColor Yellow
Write-Host "  Node: {node['name']}" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {{
    Write-Host "[!] Requesting Administrator privileges..." -ForegroundColor Yellow
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}}

Write-Host "[OK] Running with Administrator privileges" -ForegroundColor Green
Write-Host ""

# Installation directory
$installDir = "C:\\DecoyVerse"

# Step 1: Create directory
Write-Host "[1/5] Creating installation directory..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Write-Host "      Created: $installDir" -ForegroundColor Green

# Step 2: Check Python
Write-Host "[2/5] Checking Python installation..." -ForegroundColor Cyan
$pythonCmd = $null
$pythonPaths = @("python", "python3", "$env:LOCALAPPDATA\\Programs\\Python\\Python311\\python.exe", "$env:LOCALAPPDATA\\Programs\\Python\\Python310\\python.exe")

foreach ($path in $pythonPaths) {{
    try {{
        $version = & $path --version 2>&1
        if ($version -like "*Python 3*") {{
            $pythonCmd = $path
            Write-Host "      Found: $version" -ForegroundColor Green
            break
        }}
    }} catch {{}}
}}

if (-not $pythonCmd) {{
    Write-Host "      ERROR: Python 3.10+ not found!" -ForegroundColor Red
    Write-Host "      Please install from https://python.org" -ForegroundColor Yellow
    pause
    exit 1
}}

# Step 3: Copy config
Write-Host "[3/5] Installing agent configuration..." -ForegroundColor Cyan
Copy-Item "agent_config.json" "$installDir\\agent_config.json" -Force
Write-Host "      Config installed (Node: {node['name']})" -ForegroundColor Green

# Step 4: Download agent files
Write-Host "[4/5] Downloading agent files..." -ForegroundColor Cyan
$baseUrl = "https://raw.githubusercontent.com/Bhavanarisatwik/ML-modle-v0/main"
$agentFiles = @("agent.py", "agent_setup.py", "agent_config.py", "file_monitor.py", "alert_sender.py")

foreach ($file in $agentFiles) {{
    try {{
        $url = "$baseUrl/$file"
        $dest = "$installDir\\$file"
        Invoke-WebRequest -Uri $url -OutFile $dest -ErrorAction Stop
        Write-Host "      Downloaded: $file" -ForegroundColor Green
    }} catch {{
        Write-Host "      WARNING: Failed to download $file" -ForegroundColor Yellow
    }}
}}

# Step 5: Install dependencies
Write-Host "[5/5] Installing Python dependencies..." -ForegroundColor Cyan
& $pythonCmd -m pip install --quiet --upgrade pip
& $pythonCmd -m pip install --quiet requests watchdog psutil
Write-Host "      Dependencies installed!" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Agent will deploy:" -ForegroundColor Yellow
Write-Host "  - {agent_config['deployment_config']['initial_decoys']} decoy files" -ForegroundColor White
Write-Host "  - {agent_config['deployment_config']['initial_honeytokens']} honeytokens" -ForegroundColor White
Write-Host ""
Write-Host "To start the agent:" -ForegroundColor Yellow
Write-Host "  cd $installDir" -ForegroundColor White
Write-Host "  python agent.py" -ForegroundColor White
Write-Host ""

# Ask if user wants to start now
$start = Read-Host "Start agent now? (Y/n)"
if ($start -ne "n" -and $start -ne "N") {{
    Set-Location $installDir
    & $pythonCmd agent.py
}}
"""
            
            zip_file.writestr("install.ps1", install_script)
            
            # Add README
            readme = f"""# DecoyVerse Agent - Pre-Configured Installer

**Node Name:** {node['name']}
**Node ID:** {node['node_id']}
**Status:** Ready to deploy

## Quick Install (Windows)

### Option 1: PowerShell Script (Recommended)
1. Extract this ZIP file
2. Right-click `install.ps1`
3. Select "Run with PowerShell"
4. Click "Yes" when prompted for admin access
5. Follow the on-screen instructions

### Option 2: Manual Installation
1. Copy `agent_config.json` to `C:\\DecoyVerse\\`
2. Download agent files from GitHub
3. Install dependencies: `pip install requests watchdog psutil`
4. Run: `python agent.py`

## What Happens After Installation?

### Automatic Deployment
The agent will automatically:
- Deploy {agent_config['deployment_config']['initial_decoys']} decoy files
- Create {agent_config['deployment_config']['initial_honeytokens']} honeytokens
- Register all decoys with the backend
- Start monitoring for access attempts

### View in Dashboard
1. Go to DecoyVerse Dashboard
2. Navigate to "Nodes" page
3. Click on "{node['name']}"
4. View deployed decoys and their paths under "Decoys" tab

## Agent Features

✓ Auto-deploys honeytokens based on OS
✓ Monitors file access in real-time
✓ Sends alerts to backend when decoys are accessed
✓ Registers all deployed files with dashboard
✓ Shows decoy paths and access logs in UI

## System Requirements
- Windows 10/11
- Python 3.10+
- Administrator access
- Internet connection

## Support
For issues, check the DecoyVerse Dashboard or contact support.
"""
            
            zip_file.writestr("README.txt", readme)
        
        # Prepare download
        zip_buffer.seek(0)
        
        # Update node status to show installer was generated
        await db_service.update_node_status(node_id, "installer_ready")
        
        filename = f"DecoyVerse-Agent-{node['name'].replace(' ', '-')}.zip"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating installer: {e}")
        raise HTTPException(status_code=500, detail=str(e))
