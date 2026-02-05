#!/bin/bash
# DecoyVerse Agent Installer for Linux
# Usage: curl -sSL https://ml-modle-v0-1.onrender.com/install/linux | sudo bash -s -- --token=YOUR_TOKEN

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   DecoyVerse Agent Installer for Linux${NC}"
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

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] Please run as root (use sudo)${NC}"
    exit 1
fi

# Create installation directory
INSTALL_DIR="/opt/decoyverse"
echo -e "${YELLOW}[INFO] Creating installation directory: $INSTALL_DIR${NC}"
mkdir -p $INSTALL_DIR

# Check for Python
echo -e "${YELLOW}[INFO] Checking for Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}[OK] Found: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}[ERROR] Python 3 not found. Installing...${NC}"
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y python3 python3-pip
    elif command -v yum &> /dev/null; then
        yum install -y python3 python3-pip
    else
        echo -e "${RED}[ERROR] Cannot install Python. Please install manually.${NC}"
        exit 1
    fi
fi

# Create config
BACKEND_URL="https://ml-modle-v0-1.onrender.com"
EXPRESS_BACKEND_URL="https://decoyverse-v2.onrender.com"
ML_SERVICE_URL="https://ml-modle-v0-1.onrender.com"

cat > $INSTALL_DIR/agent_config.json << EOF
{
    "node_api_key": "$TOKEN",
    "backend_url": "$BACKEND_URL/api",
    "express_backend_url": "$EXPRESS_BACKEND_URL/api",
    "ml_service_url": "$ML_SERVICE_URL",
    "monitor_paths": [
        "/home",
        "/root",
        "/var/www"
    ],
    "check_interval": 5
}
EOF
echo -e "${GREEN}[OK] Created config: $INSTALL_DIR/agent_config.json${NC}"

# Create agent script
cat > $INSTALL_DIR/agent.py << 'AGENT_EOF'
#!/usr/bin/env python3
"""
DecoyVerse Lightweight Agent for Linux
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
ML_SERVICE_URL = CONFIG.get("ml_service_url", "https://ml-modle-v0-1.onrender.com")
MONITOR_PATHS = CONFIG.get("monitor_paths", [])
CHECK_INTERVAL = CONFIG.get("check_interval", 5)

# Honeytoken file patterns
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
AGENT_EOF

chmod +x $INSTALL_DIR/agent.py
echo -e "${GREEN}[OK] Created agent: $INSTALL_DIR/agent.py${NC}"

# Install dependencies
echo -e "${YELLOW}[INFO] Installing Python dependencies...${NC}"
pip3 install requests watchdog --quiet 2>/dev/null || pip install requests watchdog --quiet
echo -e "${GREEN}[OK] Dependencies installed${NC}"

# Create systemd service
cat > /etc/systemd/system/decoyverse-agent.service << EOF
[Unit]
Description=DecoyVerse Security Agent
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/agent.py
Restart=always
RestartSec=10
User=root
WorkingDirectory=$INSTALL_DIR

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable decoyverse-agent
echo -e "${GREEN}[OK] Created systemd service${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   Installation Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "To start the agent:${NC}"
echo -e "  ${CYAN}sudo systemctl start decoyverse-agent${NC}"
echo ""
echo -e "To check status:${NC}"
echo -e "  ${CYAN}sudo systemctl status decoyverse-agent${NC}"
echo ""
echo -e "To view logs:${NC}"
echo -e "  ${CYAN}sudo journalctl -u decoyverse-agent -f${NC}"
echo ""
echo -e "${YELLOW}Starting agent now...${NC}"
systemctl start decoyverse-agent
systemctl status decoyverse-agent --no-pager
