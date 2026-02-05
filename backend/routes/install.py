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
    - PowerShell installation script (with auto-start on boot)
    - Background runner script
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
        
        initial_decoys = node.get("deployment_config", {}).get("initial_decoys", 3)
        initial_honeytokens = node.get("deployment_config", {}).get("initial_honeytokens", 5)
        
        # Create agent configuration
        agent_config = {
            "node_id": node["node_id"],
            "node_api_key": node["node_api_key"],
            "node_name": node["name"],
            "os_type": node.get("os_type", "windows"),
            "backend_url": "https://ml-modle-v0-1.onrender.com/api",
            "ml_service_url": "https://ml-modle-v0-2.onrender.com",
            "deployment_config": {
                "initial_decoys": initial_decoys,
                "initial_honeytokens": initial_honeytokens,
                "deploy_path": None
            }
        }
        
        # Create in-memory ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            
            # Add agent config
            zip_file.writestr(
                "agent_config.json",
                json.dumps(agent_config, indent=2)
            )
            
            # Main installation script
            install_script = f'''# DecoyVerse Agent Installer - Complete Setup
# Pre-configured for node: {node['name']}
# This script installs and runs the agent in background with auto-start

param(
    [switch]$Silent = $false
)

$ErrorActionPreference = "Continue"
$installDir = "C:\\DecoyVerse"
$nodeName = "{node['name']}"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Status($message, $color = "White") {{
    if (-not $Silent) {{ Write-Host $message -ForegroundColor $color }}
}}

# Self-unblock this script (prevents "file is blocked" issues)
Unblock-File -Path $PSCommandPath -ErrorAction SilentlyContinue

# Banner
Write-Status "============================================" "Cyan"
Write-Status "  DecoyVerse Agent - Complete Installation" "Yellow"
Write-Status "  Node: $nodeName" "Green"
Write-Status "============================================" "Cyan"
Write-Status ""

# CRITICAL: Check if agent already installed
if (Test-Path "$installDir\\agent.py") {{
    Write-Status "" "Yellow"
    Write-Status "============================================" "Yellow"
    Write-Status "  WARNING: Agent Already Installed!" "Yellow"
    Write-Status "============================================" "Yellow"
    Write-Status "" "Yellow"
    Write-Status "An agent is already running on this system." "Yellow"
    Write-Status "Installing a second agent may cause conflicts!" "Yellow"
    Write-Status "" "Yellow"
    Write-Status "Current installation: $installDir" "Gray"
    Write-Status "" "Yellow"
    Write-Status "Options:" "Cyan"
    Write-Status "  1. Exit and use existing agent" "Gray"
    Write-Status "  2. Continue anyway (may cause issues)" "Gray"
    Write-Status "" "Yellow"
    
    if (-not $Silent) {{
        $response = Read-Host "Continue installation? (y/N)"
        if ($response -ne 'y' -and $response -ne 'Y') {{
            Write-Status "Installation cancelled." "Yellow"
            pause
            exit 0
        }}
        Write-Status "" "Yellow"
        Write-Status "Proceeding with installation..." "Yellow"
        Write-Status "Previous agent will be stopped and replaced." "Yellow"
        Write-Status "" "Yellow"
        
        # Stop existing agent processes
        Write-Status "Stopping existing agent processes..." "Yellow"
        Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {{$_.Path -like "*DecoyVerse*"}} | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }}
}}

# Check and request admin if needed
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {{
    Write-Status "[!] Requesting Administrator privileges..." "Yellow"
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}}

Write-Status "[OK] Administrator privileges confirmed" "Green"
Write-Status ""

# Step 1: Create installation directory
Write-Status "[1/7] Creating installation directory..." "Cyan"
if (-not (Test-Path $installDir)) {{
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}}
Write-Status "      Path: $installDir" "Gray"

# Step 2: Check Python
Write-Status "[2/7] Checking Python installation..." "Cyan"
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {{
    try {{
        $ver = & $cmd --version 2>&1
        if ($ver -like "*Python 3*") {{
            $pythonCmd = $cmd
            Write-Status "      Found: $ver" "Green"
            break
        }}
    }} catch {{}}
}}

if (-not $pythonCmd) {{
    Write-Status "      ERROR: Python 3.10+ required!" "Red"
    Write-Status "      Download from: https://python.org" "Yellow"
    if (-not $Silent) {{ pause }}
    exit 1
}}

# Step 3: Copy configuration
Write-Status "[3/7] Installing configuration..." "Cyan"
$configSource = Join-Path $scriptDir "agent_config.json"
if (Test-Path $configSource) {{
    Copy-Item $configSource "$installDir\\agent_config.json" -Force
    Write-Status "      Node configured: $nodeName" "Green"
}} else {{
    Write-Status "      ERROR: agent_config.json not found!" "Red"
    if (-not $Silent) {{ pause }}
    exit 1
}}

# Step 4: Download agent files
Write-Status "[4/7] Downloading agent files..." "Cyan"
$baseUrl = "https://raw.githubusercontent.com/Bhavanarisatwik/ML-modle-v0/main"
$files = @("agent.py", "agent_setup.py", "agent_config.py", "file_monitor.py", "alert_sender.py")
$downloadSuccess = $true

foreach ($file in $files) {{
    try {{
        $url = "$baseUrl/$file"
        Invoke-WebRequest -Uri $url -OutFile "$installDir\\$file" -UseBasicParsing -ErrorAction Stop
        Write-Status "      Downloaded: $file" "Gray"
    }} catch {{
        Write-Status "      WARNING: Failed to download $file" "Yellow"
        $downloadSuccess = $false
    }}
}}

if (-not $downloadSuccess) {{
    Write-Status "      Some files failed - checking existing..." "Yellow"
}}

# Step 5: Install Python dependencies
Write-Status "[5/7] Installing Python dependencies..." "Cyan"
& $pythonCmd -m pip install --quiet --upgrade pip 2>&1 | Out-Null
& $pythonCmd -m pip install --quiet requests watchdog psutil 2>&1 | Out-Null
Write-Status "      Dependencies installed" "Green"

# Step 6: Create startup task (run on boot)
Write-Status "[6/7] Setting up auto-start on boot..." "Cyan"
$taskName = "DecoyVerseAgent"
$pythonPath = (Get-Command $pythonCmd).Source
$taskAction = New-ScheduledTaskAction -Execute $pythonPath -Argument "agent.py" -WorkingDirectory $installDir
$taskTrigger = New-ScheduledTaskTrigger -AtLogon
$taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

# Remove old task if exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create new task
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -Principal $taskPrincipal -Description "DecoyVerse security monitoring agent" | Out-Null
Write-Status "      Auto-start enabled (runs at login)" "Green"

# Step 7: Start agent in background
Write-Status "[7/7] Starting agent in background..." "Cyan"
Set-Location $installDir

# Start hidden Python process
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = $pythonPath
$processInfo.Arguments = "agent.py"
$processInfo.WorkingDirectory = $installDir
$processInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$processInfo.CreateNoWindow = $true

$process = [System.Diagnostics.Process]::Start($processInfo)
Start-Sleep -Seconds 3

if ($process -and -not $process.HasExited) {{
    Write-Status "      Agent running (PID: $($process.Id))" "Green"
}} else {{
    Write-Status "      Started (checking logs for status)" "Yellow"
}}

# Done!
Write-Status ""
Write-Status "============================================" "Cyan"
Write-Status "  Installation Complete!" "Green"
Write-Status "============================================" "Cyan"
Write-Status ""
Write-Status "Agent Status:" "White"
Write-Status "  - Location: $installDir" "Gray"
Write-Status "  - Node: $nodeName" "Gray"
Write-Status "  - Decoys: {initial_decoys} files will be deployed" "Gray"
Write-Status "  - Honeytokens: {initial_honeytokens} tokens will be created" "Gray"
Write-Status "  - Auto-start: Enabled (runs at login)" "Gray"
Write-Status ""
Write-Status "The agent is now running silently in the background." "Green"
Write-Status "View deployed decoys in the DecoyVerse dashboard." "Green"
Write-Status ""
Write-Status "Useful commands:" "Yellow"
Write-Status "  Stop agent:    Stop-Process -Name python" "Gray"
Write-Status "  View logs:     Get-Content $installDir\\agent.log -Tail 50" "Gray"
Write-Status "  Check status:  Get-ScheduledTask DecoyVerseAgent" "Gray"
Write-Status ""

if (-not $Silent) {{
    pause
}}
'''
            zip_file.writestr("install.ps1", install_script)
            
            # Add README
            readme = f"""# DecoyVerse Agent - Complete Auto-Installer

**Node Name:** {node['name']}
**Node ID:** {node['node_id']}
**Status:** Ready to deploy

## Quick Install (Windows)

### IMPORTANT: If you see "Cannot be loaded" error:
Windows may block downloaded PowerShell scripts. To fix:

**Option 1 - One Command (Recommended):**
1. Extract this ZIP file
2. Open PowerShell in the extracted folder
3. Run this command:
```powershell
Unblock-File .\\install.ps1; .\\install.ps1
```

**Option 2 - GUI Method:**
1. Right-click `install.ps1` → Properties
2. Check "Unblock" at the bottom → Click OK
3. Right-click `install.ps1` → "Run with PowerShell"

**Option 3 - Bypass Method:**
```powershell
powershell -ExecutionPolicy Bypass -File .\\install.ps1
```

### After Installation

**That's it!** The agent will:
- Install to C:\\DecoyVerse
- Deploy honeytokens automatically
- Run in the background
- Start automatically on boot
- **Show up in dashboard within 1 minute**

### ⚠️ IMPORTANT: Only ONE agent per system!
If you already have an agent installed, the installer will warn you.
Running multiple agents on the same system causes conflicts!

## What Gets Installed?

### Honeytokens & Decoys
The agent deploys {initial_decoys} decoy files and {initial_honeytokens} honeytokens to strategic locations:
- ~/.aws, ~/.ssh, ~/.azure (cloud credentials)
- Documents, Desktop (user files)
- Realistic-looking credential files

### Background Monitoring
- Runs silently in the background
- Monitors for file access attempts
- Sends alerts to dashboard in real-time

### Auto-Start on Boot
- Scheduled task runs agent when you log in
- Survives restarts automatically
- No manual intervention needed

## View in Dashboard

After installation:
1. Go to DecoyVerse Dashboard
2. Navigate to "Nodes" → "{node['name']}"
3. See deployed decoys under "Decoys" tab
4. Monitor alerts in "Alerts" page

## Commands

```powershell
# Check agent status
Get-ScheduledTask DecoyVerseAgent

# Stop agent
Stop-ScheduledTask DecoyVerseAgent

# Start agent  
Start-ScheduledTask DecoyVerseAgent

# Uninstall
Unregister-ScheduledTask DecoyVerseAgent -Confirm:$false
Remove-Item C:\\DecoyVerse -Recurse
```

## Requirements
- Windows 10/11
- Python 3.10+
- Admin access (for installation only)
- Internet connection

## Troubleshooting

**Agent not running?**
```powershell
cd C:\\DecoyVerse
python agent.py
```

**Need to reinstall?**
Run install.ps1 again - it will clean up and reinstall.
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
