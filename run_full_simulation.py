import os
import time
import requests
import json
import uuid
import threading
import sys
from pathlib import Path

# Add current dir so it can import agent modules
sys.path.insert(0, ".")

base_url = "https://ml-modle-v0-1.onrender.com"

print("=" * 60)
print("🛡️  DecoyVerse Autonomous Attack Simulation 🛡️")
print("=" * 60)

# 1. Register User
email = f"simulator_{uuid.uuid4().hex[:6]}@example.com"
password = "Password123!"

print(f"\n[1] Registering test user: {email}")
resp = requests.post(f"{base_url}/auth/register", json={"email": email, "password": password})
if resp.status_code != 200:
    print(f"❌ Failed to register: {resp.text}")
    sys.exit(1)
token = resp.json()
jwt = token.get("access_token", token)
if type(token) is dict:
    jwt = token.get("access_token")

headers = {"Authorization": f"Bearer {jwt}"}
print("✅ Registration successful. JWT obtained.")

# 2. Create Node
print("\n[2] Registering User Node...")
node_data = {
    "name": "Validation Target Node",
    "os_type": "windows",
    "deployment_config": {
        "decoys": [
            {"type": "fake_credentials", "file_name": "aws_keys.txt"}
        ]
    }
}
resp = requests.post(f"{base_url}/nodes", json=node_data, headers=headers)
if resp.status_code != 200:
    print(f"❌ Failed to create node: {resp.text}")
    sys.exit(1)
node_info = resp.json()
node_id = node_info["node_id"]
node_api_key = node_info["node_api_key"]
print(f"✅ Node created! ID: {node_id}")

# 3. Configure Local Agent
print("\n[3] Generating local agent configuration...")
config = {
    "node_id": node_id,
    "node_api_key": node_api_key,
    "backend_url": f"{base_url}"
}
with open("agent_config.json", "w") as f:
    json.dump(config, f, indent=2)
print("✅ Created agent_config.json")

# 4. Background execution of the Agent
def run_agent():
    try:
        from agent import DeceptionAgent
        agent = DeceptionAgent()
        agent.setup_honeytokens()
        agent.initialize_monitoring()
        agent.check_backend()
        
        start_time = time.time()
        print("\n[AGENT] 🏃 Agent started tracking directory.")
        # Monitor for exactly 30s
        while time.time() - start_time < 30:
            alerts = agent.monitor.monitor_once(callback=None)
            if alerts:
                for alert in alerts:
                    print(f"\n[AGENT] ⚠️ Detected file access on {alert['file_accessed']}. Dispatching to API!")
                    success = agent.sender.send_alert(alert)
                    if success:
                        print(f"[AGENT] 🧠 Alert successfully broadcasted to central server.")
            time.sleep(2)
        print("\n[AGENT] 🛑 Shutting down monitoring loop.")
    except Exception as e:
        print(f"\n[AGENT FATAL] Error running agent: {e}")

agent_thread = threading.Thread(target=run_agent, daemon=True)
agent_thread.start()

print("\n[4] Allowing 8 seconds for agent to fully drop decoys and stabilize file events...")
time.sleep(8)  # Let agent stabilize

# 5. Simulate the Attack
honeytoken_path = Path("system_cache") / "aws_keys.txt"
if honeytoken_path.exists():
    print(f"\n[5] 🥷 Simulating Malicious Threat: Opening and reading {honeytoken_path}...")
    try:
        with open(honeytoken_path, 'r') as f:
            content = f.read()
        print("✅ Honeytoken opened locally successfully! Trap sprung.")
    except Exception as e:
        print(f"❌ Error triggering attack: {e}")
else:
    print("\n❌ CRITICAL: Honeytoken file was not dropped in system_cache!")

# Give time for agent to catch event, beam to ML server, and database commit
print("\n[6] Waiting 6 seconds for ML processing and telemetry propagation...")
time.sleep(6)

# 6. Verify Alerts Triggered in Database
print("\n[7] Querying Backend Database for resulting AI Insights and Alerts...")
resp = requests.get(f"{base_url}/api/alerts", headers=headers)
if resp.status_code == 200:
    data = resp.json()
    alerts = data.get("alerts", data) if type(data) is dict else data
    if len(alerts) > 0:
        latest = alerts[0]
        print(f"\n🛡️ SUCCESS! Backend confirmed alert!")
        print(f"  → File: {latest.get('related_decoy')}")
        print(f"  → Attack Classification: {latest.get('attack_type')}")
        print(f"  → Risk Score: {latest.get('risk_score')}")
        print(f"  → Confidence: {latest.get('confidence')}")
    else:
        print("\n❌ Result returned with 0 recorded alerts. Something failed along the chain.")
else:
    print(f"\n❌ Error fetching alerts: {resp.text}")

print("\nCleanup: Forcing thread stop.")
