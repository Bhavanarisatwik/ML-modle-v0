#!/bin/bash
# DecoyVerse Agent Installer for macOS
# Usage: curl -sSL https://ml-modle-v0-1.onrender.com/install/macos | sudo bash -s -- --token=YOUR_TOKEN

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   DecoyVerse Agent Installer for macOS${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Parse arguments
TOKEN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --token=*)
            TOKEN="${1#*=}"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Check for token
if [ -z "$TOKEN" ]; then
    echo -e "${RED}[ERROR] No token provided. Use --token=YOUR_TOKEN${NC}"
    exit 1
fi

echo -e "${GREEN}[INFO] Token: ${TOKEN:0:10}...${NC}"

# Create installation directory
INSTALL_DIR="/usr/local/decoyverse"
echo -e "${YELLOW}[INFO] Creating installation directory: $INSTALL_DIR${NC}"
sudo mkdir -p $INSTALL_DIR

# Check for Python
echo -e "${YELLOW}[INFO] Checking for Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}[OK] Found: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}[ERROR] Python 3 not found. Install with: brew install python3${NC}"
    exit 1
fi

# Create config
BACKEND_URL="https://ml-modle-v0-1.onrender.com"
EXPRESS_BACKEND_URL="https://decoyverse-v2.onrender.com"
ML_SERVICE_URL="https://ml-modle-v0-1.onrender.com"

sudo tee $INSTALL_DIR/agent_config.json > /dev/null << EOF
{
    "node_api_key": "$TOKEN",
    "backend_url": "$BACKEND_URL/api",
    "express_backend_url": "$EXPRESS_BACKEND_URL/api",
    "ml_service_url": "$ML_SERVICE_URL",
    "monitor_paths": [
        "$HOME/Documents",
        "$HOME/Desktop",
        "$HOME/Downloads"
    ],
    "check_interval": 5
}
EOF
echo -e "${GREEN}[OK] Created config: $INSTALL_DIR/agent_config.json${NC}"

# Create agent script
sudo tee $INSTALL_DIR/agent.py > /dev/null << 'AGENT_EOF'
#!/usr/bin/env python3
"""
DecoyVerse Lightweight Agent for macOS
Monitors honeytoken files and reports access to backend
"""

import os
import sys
import json
import time
import socket
import requests
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("[ERROR] watchdog not installed. Run: pip3 install watchdog")
    sys.exit(1)

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_config.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

NODE_API_KEY = CONFIG.get("node_api_key", "")
BACKEND_URL = CONFIG.get("backend_url", "https://ml-modle-v0-1.onrender.com/api")
MONITOR_PATHS = CONFIG.get("monitor_paths", [])
CHECK_INTERVAL = CONFIG.get("check_interval", 5)

HONEYTOKEN_PATTERNS = [
    "passwords", "credentials", "secret", "api_key", "token",
    "backup", "confidential", "private", "admin", "root", ".ssh", "id_rsa"
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
        now = time.time()
        if path in self.last_report and now - self.last_report[path] < 60:
            return
        self.last_report[path] = now
        self.report_access(path, event.event_type)
    
    def report_access(self, file_path, action):
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "hostname": socket.gethostname(),
                "username": os.getenv("USER", "unknown"),
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
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            observer.schedule(handler, expanded, recursive=True)
            print(f"[OK] Watching: {expanded}")
        else:
            print(f"[WARN] Path not found: {expanded}")
    
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
AGENT_EOF

sudo chmod +x $INSTALL_DIR/agent.py
echo -e "${GREEN}[OK] Created agent: $INSTALL_DIR/agent.py${NC}"

# Install dependencies
echo -e "${YELLOW}[INFO] Installing Python dependencies...${NC}"
pip3 install requests watchdog --quiet 2>/dev/null || pip install requests watchdog --quiet
echo -e "${GREEN}[OK] Dependencies installed${NC}"

# Create LaunchDaemon
sudo tee /Library/LaunchDaemons/com.decoyverse.agent.plist > /dev/null << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.decoyverse.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$INSTALL_DIR/agent.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>StandardOutPath</key>
    <string>/var/log/decoyverse-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/decoyverse-agent.log</string>
</dict>
</plist>
EOF

echo -e "${GREEN}[OK] Created LaunchDaemon${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   Installation Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "To start the agent:${NC}"
echo -e "  ${CYAN}sudo launchctl load /Library/LaunchDaemons/com.decoyverse.agent.plist${NC}"
echo ""
echo -e "To stop the agent:${NC}"
echo -e "  ${CYAN}sudo launchctl unload /Library/LaunchDaemons/com.decoyverse.agent.plist${NC}"
echo ""
echo -e "To view logs:${NC}"
echo -e "  ${CYAN}tail -f /var/log/decoyverse-agent.log${NC}"
echo ""
echo -e "${YELLOW}Starting agent now...${NC}"
sudo launchctl load /Library/LaunchDaemons/com.decoyverse.agent.plist
echo -e "${GREEN}Agent started!${NC}"
