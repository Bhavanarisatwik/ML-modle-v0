# DecoyVerse Agent: Capabilities & Limitations Report

This document outlines the exact capabilities, detection mechanisms, and inherent limitations of the DecoyVerse-v2 endpoint deception agent (`agent.py`) that runs on monitored host nodes.

## 🎯 Core Concept
The DecoyVerse agent operates on the principle of **cyber deception**. Instead of relying on signature-based detection or heuristics like traditional Antivirus (AV), the agent acts as a sensor by planting traps (honeytokens). Any interaction with these traps guarantees zero false positives because legitimate users and processes have no operational reason to interact with them.

---

## 🟢 What the Agent CAN Detect & Perform (Capabilities)

### 1. Honeytoken Deployment & Management
*   **Dynamic Baiting**: The agent can automatically deploy various types of high-fidelity fake files across the file system (e.g., hidden `system_cache` folder or scattered across standard profile folders like `Documents`, `.aws`, `.ssh`, etc.).
*   **Bait Types**:
    *   `aws_keys.txt` (Credential theft)
    *   `db_creds.env` (Database configuration theft)
    *   `employee_salary.xlsx` (Data exfiltration)
    *   `server_backup.sql` (Database dump theft)
    *   `api_keys.json` (API key theft)
*   **Lifecycle Management**: Cleanly keeps track of deployed files via a manifest and can securely remove them upon remote uninstall commands.

### 2. File Access Detection
*   **Real-time Monitoring**: Uses the `watchdog` library leveraging Windows `ReadDirectoryChangesW` mixed with a stat-polling fallback to monitor the deployed honeytokens.
*   **Event Types**: Detects `MODIFIED`, `ACCESSED`, and `DELETED` events on the planted bait files.
*   **Process Enrichment**: When a file is accessed, the agent uses `psutil` to identify the malicious process. It successfully grabs the:
    *   Process ID (PID)
    *   Process Name
    *   Command Line arguments (first 300 characters)
    *   User context executing the process

### 3. Network Outbound Traffic Analysis
The agent runs a background thread (`network_monitor.py`) polling `psutil.net_connections` every 30 seconds to score unusual network patterns using a custom 8-rule engine.
*   **Port Scans**: Detects if the host connects to 15+ unique destination ports within a 120-second rolling window.
*   **C2 Beacons**: Detects repetitive connections to the same non-standard port indicating potential Command and Control traffic.
*   **High Rate Connections**: Detects abnormal spikes in connection counts (50+ connections in 120s).
*   **High-Risk Terminations**: Immediately flags connections to universally malicious ports (e.g., `4444`, `4445` for Metasploit, `31337`, `6666` IRC, etc.).

### 4. Privilege-Separated Mitigation (Firewall Blocking)
*   **Least Privilege Agent**: The main tracking agent runs as a **normal standard user**, minimizing its attack surface if exploited.
*   **Auto-Isolation**: The agent securely queues attacker IP addresses to a local `pending_blocks.json` file.
*   **SYSTEM Execution**: A separate component (`dv_firewall.py`) running as a scheduled task under `SYSTEM` privileges polls these requests and safely applies Windows Firewall blocks (Inbound and Outbound) to lock out the attacker.

### 5. Secure Backend Communications
*   **API Authentication**: Securely registers with the backend using Node IDs and hashed API Keys (`X-Node-Id`, `X-Node-Key`) to prevent alert spoofing.
*   **Heartbeating**: Relays health status and pulls dynamic configuration updates (like deploying more honeytokens) natively.

---

## 🔴 What the Agent CANNOT Detect & Limitations

### 1. Network Monitoring Blind Spots
*   **Polling Frequency (30s Gap)**: Because the network monitor polls every 30 seconds rather than capturing raw packets (e.g., via a driver), **highly ephemeral connections** (lasting only a few seconds between polls) will be missed.
*   **Kernel-Level Rootkits**: Threat actors utilizing advanced rootkits or Bring Your Own Vulnerable Driver (BYOVD) techniques to hide connections from the Windows API (`psutil`) will bypass the network monitor.
*   **Payload Ignorance**: It does not perform Deep Packet Inspection (DPI). The agent analyzes connection metadata (IP, Port, Rate), but it cannot see what data is actually being sent inside the connection.
*   **Legitimate Datalink Lateral Movement**: The network engine ignores trusted / standard ports (like 443/HTTPS, 445/SMB, 3389/RDP). Unless the traffic exceeds massive rate limits, lateral movement using built-in Windows protocols will largely go unflagged.

### 2. File System Monitoring Blind Spots
*   **Evasion by Omission**: The entire concept of cyber deception requires the attacker to *fall for the trap*. If an attacker carefully scans the system, spots the honeytokens as fake, and avoids interacting with them entirely, the file deception fails to trigger.
*   **'Last Access' Reliance**: On Windows, the "accessed" event can be tricky. It often relies on Windows updating the file's Last Access Time or triggering `FILE_NOTIFY_CHANGE_LAST_ACCESS`. Some heavily customized or hardened Windows environments might disable last access time updates to save disk I/O, which could slightly degrade "read-only" detection if watchdog misses the open handle.

### 3. Process Enrichment Limits
*   **Privilege Walls**: Process tracing is "best-effort." Because the agent runs as a standard user, if an attacker executes file access via a `SYSTEM` process or another elevated Administrator context, `psutil.AccessDenied` might trigger, meaning the alert is recorded but the **offending process metadata** will be blank.

---
### Summary
The agent is highly effective at acting as a **post-breach tripwire**, offering highly accurate alerts with basically zero false positives based on deception, combined with network metadata scoring. It relies on the environment operating somewhat normally at the user-space level, and it is NOT a drop-in replacement for low-level memory AV or kernel-level EDR systems.

---

## 📋 Data Processing & Features Summary

1️⃣ **Agent Capabilities**
- Honeytoken deployment and detection (fake credentials, DB keys, AWS tokens)
- Suspicious file access monitoring
- Port scan detection (multiple unique ports in a short window)
- C2 beacon detection (repeated connections to non-standard ports)
- High-rate connection monitoring (potential brute-force or bulk transfers)
- High-risk port connections (detects connections to known malicious ports like 1337, 4444)
- Process & command-line enrichment (captures PID and command line args of offending processes)
- Automated local firewall isolation (blocks identified attacker IPs internally)

2️⃣ **Data Sources (What the agent reads)**
- File system events (via Windows ReadDirectoryChangesW for honeytoken access)
- Active network connections (via `psutil.net_connections`)
- Process metadata (via `psutil` to extract PID, name, user, and command line)
- System context (Hostname, specific OS execution environments)

3️⃣ **ML Model Inputs**
- `failed_logins`: Count of failed login attempts
- `request_rate`: HTTP requests / network connections rate
- `commands_count`: Number of unique commands or ports connected to
- `sql_payload`: Binary flag for SQL injection 
- `honeytoken_access`: Binary flag (1 if honeytoken was accessed)
- `session_time`: Session duration in seconds
- `dest_port`: Destination port of network connection
- `is_high_risk_port`: Binary flag for known malicious/exploitable ports
- `rule_score`: Heuristic score calculated manually by the agent

4️⃣ **ML Outputs**
- `attack_type`: Attacker classification (e.g., DataExfil, Injection, BruteForce, Recon, Normal)
- `risk_score`: Threat level indicating severity (Scale of 1 to 10)
- `confidence`: Certainty percentage of the classification prediction
- `anomaly_score`: Raw anomaly deviation score
- `is_anomaly`: Boolean true/false indicating if behavior deviates from baseline

5️⃣ **Alert Types**
- `HONEYTOKEN_ACCESS`: Alert when a decoy file is modified, accessed, or deleted
- `port_scan`: Alert for unusual network probing
- `c2_beacon`: Alert for command and control-like traffic patterns
- `high_rate`: Alert for abnormal network connection counts
- `high_risk_port`: Alert for connections directly to common malware ports
- `non_std_port`: Alert for any general outbound traffic to unusual ports

6️⃣ **Dashboard Metrics**
- Active attackers tracked by ID/IP
- Attack timeline and real-time logs
- Attack type distribution (charts showing Recon vs DataExfil, etc.)
- Risk scores and confidence intervals
- Endpoint / node health (agent check-in status)
- Active blocks (list of IPs isolated by the firewall)
