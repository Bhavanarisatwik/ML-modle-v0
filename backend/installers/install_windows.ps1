# DecoyVerse Agent Installer for Windows
# Run as Administrator

param(
    [string]$Token = $env:DECOY_TOKEN
)

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   DecoyVerse Agent Installer for Windows" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check for admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Please run this script as Administrator" -ForegroundColor Red
    exit 1
}

# Check for token
if (-not $Token) {
    Write-Host "[ERROR] No token provided. Set DECOY_TOKEN environment variable or pass -Token parameter" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Token: $($Token.Substring(0, 10))..." -ForegroundColor Green

# Create installation directory
$InstallDir = "C:\DecoyVerse"
Write-Host "[INFO] Creating installation directory: $InstallDir" -ForegroundColor Yellow

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# Check for Python
Write-Host "[INFO] Checking for Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found. Please install Python 3.8+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Download agent files from backend
$BackendUrl = "https://ml-modle-v0-1.onrender.com"
Write-Host "[INFO] Downloading agent files from $BackendUrl..." -ForegroundColor Yellow

# Create agent config
$ConfigPath = "$InstallDir\agent_config.json"
$Config = @{
    node_api_key = $Token
    backend_url = "$BackendUrl/api"
    ml_service_url = "https://ml-modle-v0-2.onrender.com"
    monitor_paths = @(
        "$env:USERPROFILE\Documents",
        "$env:USERPROFILE\Desktop"
    )
    check_interval = 5
} | ConvertTo-Json -Depth 3

$Config | Out-File -FilePath $ConfigPath -Encoding UTF8
Write-Host "[OK] Created config: $ConfigPath" -ForegroundColor Green

# Download agent script
$AgentScript = @'
#!/usr/bin/env python3
"""
DecoyVerse Lightweight Agent for Windows
Monitors honeytoken files and reports access to backend
"""

import os
import sys
import json
import time
import socket
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent_config.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

NODE_API_KEY = CONFIG.get("node_api_key", "")
BACKEND_URL = CONFIG.get("backend_url", "https://ml-modle-v0-1.onrender.com/api")
ML_SERVICE_URL = CONFIG.get("ml_service_url", "https://ml-modle-v0-2.onrender.com")
MONITOR_PATHS = CONFIG.get("monitor_paths", [])
CHECK_INTERVAL = CONFIG.get("check_interval", 5)

# Honeytoken file patterns
HONEYTOKEN_PATTERNS = [
    "passwords", "credentials", "secret", "api_key", "token",
    "backup", "confidential", "private", "admin", "root"
]

class HoneytokenHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_report = {}
    
    def is_honeytoken(self, path):
        name = os.path.basename(path).lower()
        return any(pattern in name for pattern in HONEYTOKEN_PATTERNS)
    
    def on_any_event(self, event):
        if event.is_directory:
            return
        
        path = event.src_path
        if not self.is_honeytoken(path):
            return
        
        # Rate limit: 1 report per file per minute
        now = time.time()
        if path in self.last_report and now - self.last_report[path] < 60:
            return
        self.last_report[path] = now
        
        # Report to backend
        self.report_access(path, event.event_type)
    
    def report_access(self, file_path, action):
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "hostname": socket.gethostname(),
                "username": os.getenv("USERNAME", "unknown"),
                "file_accessed": os.path.basename(file_path),
                "file_path": file_path,
                "action": action.upper(),
                "severity": "HIGH",
                "alert_type": "HONEYTOKEN_ACCESS"
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Node-API-Key": NODE_API_KEY
            }
            
            response = requests.post(
                f"{BACKEND_URL}/agent-alert",
                json=payload,
                headers=headers,
                timeout=10
            )
            print(f"[ALERT] Reported: {file_path} ({action}) -> {response.status_code}")
        except Exception as e:
            print(f"[ERROR] Failed to report: {e}")

def main():
    print("=" * 50)
    print("DecoyVerse Agent Started")
    print(f"Backend: {BACKEND_URL}")
    print(f"Monitoring: {MONITOR_PATHS}")
    print("=" * 50)
    
    handler = HoneytokenHandler()
    observer = Observer()
    
    for path in MONITOR_PATHS:
        if os.path.exists(path):
            observer.schedule(handler, path, recursive=True)
            print(f"[OK] Watching: {path}")
        else:
            print(f"[WARN] Path not found: {path}")
    
    observer.start()
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()
    print("Agent stopped.")

if __name__ == "__main__":
    main()
'@

$AgentPath = "$InstallDir\agent.py"
$AgentScript | Out-File -FilePath $AgentPath -Encoding UTF8
Write-Host "[OK] Created agent: $AgentPath" -ForegroundColor Green

# Install dependencies
Write-Host "[INFO] Installing Python dependencies..." -ForegroundColor Yellow
pip install requests watchdog --quiet
Write-Host "[OK] Dependencies installed" -ForegroundColor Green

# Create start script
$StartScript = @"
@echo off
cd /d "$InstallDir"
python agent.py
pause
"@
$StartPath = "$InstallDir\start_agent.bat"
$StartScript | Out-File -FilePath $StartPath -Encoding ASCII
Write-Host "[OK] Created start script: $StartPath" -ForegroundColor Green

# Create Windows Service (optional)
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   Installation Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the agent manually:" -ForegroundColor White
Write-Host "  cd $InstallDir" -ForegroundColor Cyan
Write-Host "  python agent.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "Or double-click: $StartPath" -ForegroundColor Yellow
Write-Host ""
Write-Host "The agent will monitor Documents and Desktop for honeytoken access." -ForegroundColor White
