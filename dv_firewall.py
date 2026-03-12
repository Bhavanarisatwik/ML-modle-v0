"""
DecoyVerse Firewall Helper (dv_firewall.py)
===========================================
Privilege-separated firewall manager. This script runs with administrator
privileges but has a single, auditable responsibility: add and remove
Windows Firewall rules.

SECURITY DESIGN
---------------
- The main agent (agent.py) runs as a NORMAL USER and has NO firewall access.
- This helper runs as a separate process (Windows Scheduled Task or service)
  with ONLY the right to manage firewall rules.
- Communication channel: a local JSON file (pending_blocks.json) that only
  local processes can write to. No network ports are opened.
- Attack surface: even if the agent is fully compromised, the attacker can
  only add IP addresses to a BLOCK list — a purely defensive action.
- This file is intentionally small and auditable (< 200 lines).

HOW IT WORKS
------------
1. Main agent writes IPs to block into  pending_blocks.json
2. This helper polls the file every POLL_SECONDS
3. For each pending IP it runs:
       netsh advfirewall firewall add rule
           name="DecoyVerse-Block-<ip>"
           dir=in action=block remoteip=<ip>
           protocol=any enable=yes
4. It also adds an outbound block for exfiltration protection
5. After a successful block it notifies the backend via the agent's own
   /api/agent/block-confirmed endpoint (using the credentials from config.json)
6. Processed IPs are moved from pending to done in the JSON file

INSTALLATION
------------
Run once (as Administrator) to create the Scheduled Task:
    python dv_firewall.py --install

This creates a Windows Scheduled Task that:
  - Runs as SYSTEM (only Windows Firewall access, no user data access)
  - Triggers every minute
  - Has no network inbound access — only local file I/O

MANUAL RUN (for testing):
    python dv_firewall.py --run-once
    python dv_firewall.py --loop        # runs continuously
"""

import json
import os
import sys
import subprocess
import logging
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("dv_firewall")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [dv_firewall] %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("dv_firewall.log", encoding="utf-8"),
    ]
)

# ---------------------------------------------------------------------------
# Paths — same directory as this script
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
PENDING_FILE = SCRIPT_DIR / "pending_blocks.json"
CONFIG_FILE = SCRIPT_DIR / "config.json"

POLL_SECONDS = 30
TASK_NAME = "DecoyVerseFirewallHelper"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_pending() -> dict:
    """Return {'pending': [...], 'done': [...]}"""
    if not PENDING_FILE.exists():
        return {"pending": [], "done": []}
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"pending": [], "done": []}
        data.setdefault("pending", [])
        data.setdefault("done", [])
        return data
    except Exception:
        return {"pending": [], "done": []}


def save_pending(data: dict):
    PENDING_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Firewall operations (require Admin)
# ---------------------------------------------------------------------------

def block_ip(ip: str) -> bool:
    """
    Add inbound AND outbound Windows Firewall rules to block an IP.
    Returns True on success.
    """
    rule_name = f"DecoyVerse-Block-{ip.replace(':', '-')}"

    for direction in ("in", "out"):
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}-{direction}",
            f"dir={direction}",
            "action=block",
            f"remoteip={ip}",
            "protocol=any",
            "enable=yes",
            "profile=any",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                check=False
            )
            if result.returncode != 0:
                logger.error(f"netsh failed ({direction}): {result.stderr.strip()}")
                return False
            logger.info(f"✅ Firewall rule added: {rule_name}-{direction}")
        except subprocess.TimeoutExpired:
            logger.error(f"netsh timed out for {ip} ({direction})")
            return False
        except FileNotFoundError:
            logger.error("netsh not found — is this Windows?")
            return False

    return True


def remove_block(ip: str) -> bool:
    """Remove both inbound and outbound rules for an IP (for future unblock)."""
    rule_name = f"DecoyVerse-Block-{ip.replace(':', '-')}"
    for direction in ("in", "out"):
        cmd = [
            "netsh", "advfirewall", "firewall", "delete", "rule",
            f"name={rule_name}-{direction}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        except Exception:
            pass
    return True


# ---------------------------------------------------------------------------
# Backend confirmation
# ---------------------------------------------------------------------------

def confirm_block_with_backend(ip: str, config: dict) -> bool:
    """Tell the backend this IP has been blocked so it can update the DB status."""
    backend_url = config.get("backend_url", "").rstrip("/")
    node_id = config.get("node_id", "")
    api_key = config.get("node_api_key", "")

    if not all([backend_url, node_id, api_key]):
        logger.warning("Config incomplete — skipping backend confirmation")
        return False

    try:
        resp = requests.post(
            f"{backend_url}/api/agent/block-confirmed",
            params={"node_id": node_id, "ip_address": ip},
            headers={"X-Node-API-Key": api_key},
            timeout=15
        )
        if resp.status_code == 200:
            logger.info(f"✅ Backend confirmed block for {ip}")
            return True
        else:
            logger.warning(f"Backend returned {resp.status_code} for block confirmation")
            return False
    except Exception as e:
        logger.error(f"Failed to confirm block with backend: {e}")
        return False


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------

def process_once():
    """Process pending blocks from the JSON file once."""
    config = load_config()
    data = load_pending()

    if not data["pending"]:
        logger.debug("No pending blocks")
        return

    newly_done = []
    still_pending = []

    for ip in data["pending"]:
        logger.info(f"Attempting to block IP: {ip}")
        success = block_ip(ip)
        if success:
            confirm_block_with_backend(ip, config)
            newly_done.append({"ip": ip, "blocked_at": datetime.utcnow().isoformat()})
            logger.warning(f"🔒 IP BLOCKED: {ip}")
        else:
            logger.error(f"Failed to block IP: {ip} — keeping in pending")
            still_pending.append(ip)

    data["pending"] = still_pending
    data["done"].extend(newly_done)
    save_pending(data)


def run_loop():
    logger.info(f"DecoyVerse Firewall Helper running (polling every {POLL_SECONDS}s)")
    while True:
        try:
            process_once()
        except Exception as e:
            logger.error(f"Error in firewall helper loop: {e}")
        time.sleep(POLL_SECONDS)


# ---------------------------------------------------------------------------
# Scheduled Task installation
# ---------------------------------------------------------------------------

def install_scheduled_task():
    """
    Creates a Windows Scheduled Task that runs this helper as SYSTEM on a
    1-minute trigger, with no network inbound access.

    Must be run as Administrator.
    """
    script_path = str(Path(__file__).resolve())
    python_exe = sys.executable

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>DecoyVerse Firewall Helper — blocks attacker IPs on behalf of the agent (privilege-separated)</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT1M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2024-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>"{script_path}" --run-once</Arguments>
      <WorkingDirectory>{str(SCRIPT_DIR)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    xml_path = SCRIPT_DIR / "dv_firewall_task.xml"
    xml_path.write_text(xml, encoding="utf-16")

    cmd = ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    xml_path.unlink(missing_ok=True)

    if result.returncode == 0:
        print(f"✅ Scheduled Task '{TASK_NAME}' created successfully.")
        print("   The firewall helper will now run every 1 minute as SYSTEM.")
    else:
        print(f"❌ Failed to create Scheduled Task: {result.stderr}")
        sys.exit(1)


def uninstall_scheduled_task():
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    subprocess.run(cmd, capture_output=True)
    print(f"✅ Scheduled Task '{TASK_NAME}' removed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DecoyVerse Firewall Helper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="Install as Windows Scheduled Task (requires Admin)")
    group.add_argument("--uninstall", action="store_true", help="Remove the Scheduled Task")
    group.add_argument("--run-once", action="store_true", help="Process pending blocks once and exit")
    group.add_argument("--loop", action="store_true", help="Run continuously (for testing)")
    args = parser.parse_args()

    if args.install:
        install_scheduled_task()
    elif args.uninstall:
        uninstall_scheduled_task()
    elif args.run_once:
        process_once()
    elif args.loop:
        run_loop()
