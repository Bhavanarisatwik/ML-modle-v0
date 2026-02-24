"""
DecoyVerse Network Monitor
==========================
Runs as a background thread inside the agent process (normal user privileges).

What it does:
  - Polls psutil.net_connections() every POLL_INTERVAL seconds
  - Filters connections to non-standard ports (suspicious traffic only)
  - Applies rule-based scoring for common attack patterns
  - Optionally sends to the ML service for a second opinion
  - POSTs high-scoring events to /api/network-event

Rule engine (Phase 1):
  port_scan       - many unique destination ports in a short window  → score 8
  c2_beacon       - repeated outbound to same non-std port            → score 7
  high_rate       - connection count spike                            → score 8
  non_std_outbound - single connection to unusual port (low score)   → score 4

ML integration (Phase 1, optional):
  If ML_PREDICT_ENDPOINT is set, sends a feature vector and uses the returned
  risk_score.  Falls back to rule score if ML call fails.

Privilege note:
  This module requires NO admin rights.  The actual firewall blocking is
  handled by dv_firewall.py which is a separate, minimal-privilege process.
"""

import threading
import time
import logging
import requests
import socket
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standard / trusted ports — connections to these are NOT flagged
# ---------------------------------------------------------------------------
STANDARD_PORTS: Set[int] = {
    20, 21,       # FTP
    22,           # SSH
    23,           # Telnet (old but common)
    25, 465, 587, # SMTP
    53,           # DNS
    80, 8080,     # HTTP
    110, 995,     # POP3
    143, 993,     # IMAP
    389, 636,     # LDAP
    443, 8443,    # HTTPS
    445,          # SMB
    1433,         # MSSQL
    1521,         # Oracle
    3306,         # MySQL
    3389,         # RDP
    5432,         # PostgreSQL
    5985, 5986,   # WinRM
    6379,         # Redis
    8001, 8000,   # Common dev/API ports (our own backend)
    9200, 9300,   # Elasticsearch
    27017,        # MongoDB
}

# Ports that are almost always malicious when seen as outbound destinations
HIGH_RISK_PORTS: Set[int] = {
    4444, 4445,   # Metasploit default shells
    1337,         # Common backdoor
    6666, 6667,   # IRC (C2 beacons)
    31337,        # Classic "elite" backdoor
    12345,        # NetBus
    5555,         # Android ADB / common shell
    9001, 9002,   # Tor default
}

POLL_INTERVAL = 30          # seconds between polls
WINDOW_SECONDS = 120        # look-back window for pattern analysis
SCAN_PORT_THRESHOLD = 15    # unique dest ports in window → port scan
RATE_THRESHOLD = 50         # connections per window → high rate
BEACON_THRESHOLD = 4        # repeated connections to same non-std port → C2
RISK_THRESHOLD = 7          # score at or above this → send alert


class ConnectionWindow:
    """Sliding time-window of observed connections for pattern analysis"""

    def __init__(self, window_seconds: int = WINDOW_SECONDS):
        self.window = window_seconds
        # dest_ip -> list of (timestamp, port)
        self._by_dest: Dict[str, List[tuple]] = defaultdict(list)
        # dest_port -> connection count
        self._port_counts: Dict[int, int] = defaultdict(int)
        self._all: List[tuple] = []  # (timestamp, dest_ip, dest_port)

    def add(self, dest_ip: str, dest_port: int):
        now = datetime.utcnow()
        self._all.append((now, dest_ip, dest_port))
        self._by_dest[dest_ip].append((now, dest_port))
        self._port_counts[dest_port] += 1

    def _prune(self):
        cutoff = datetime.utcnow() - timedelta(seconds=self.window)
        self._all = [(t, ip, p) for t, ip, p in self._all if t > cutoff]
        for ip in list(self._by_dest.keys()):
            self._by_dest[ip] = [(t, p) for t, p in self._by_dest[ip] if t > cutoff]
            if not self._by_dest[ip]:
                del self._by_dest[ip]

    def unique_dest_ports(self) -> Set[int]:
        self._prune()
        return {p for _, _, p in self._all}

    def total_count(self) -> int:
        self._prune()
        return len(self._all)

    def connections_to_port(self, port: int) -> int:
        self._prune()
        return sum(1 for _, _, p in self._all if p == port)


class NetworkMonitor:
    """
    Background thread that watches network connections for suspicious activity.
    Runs with normal user privileges.
    """

    def __init__(self, backend_url: str, node_id: str, node_api_key: str,
                 ml_predict_endpoint: Optional[str] = None):
        self.backend_url = backend_url.rstrip("/")
        self.node_id = node_id
        self.node_api_key = node_api_key
        self.ml_endpoint = ml_predict_endpoint
        self._window = ConnectionWindow()
        self._seen_connections: Set[tuple] = set()   # (dest_ip, dest_port) dedup in same poll
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="dv-network-monitor")
        self._thread.start()
        logger.info("🔍 Network monitor started")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Network monitor stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._poll()
            except Exception as e:
                logger.error(f"Network monitor poll error: {e}")
            self._stop_event.wait(POLL_INTERVAL)

    def _poll(self):
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not installed — network monitoring disabled. Run: pip install psutil")
            self._stop_event.set()
            return

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError) as e:
            logger.warning(f"Cannot read net_connections (permissions): {e}")
            return

        suspicious: List[Dict[str, Any]] = []

        for conn in connections:
            # Only care about ESTABLISHED outbound connections
            if conn.status != "ESTABLISHED":
                continue
            if conn.raddr is None:
                continue

            dest_ip, dest_port = conn.raddr.ip, conn.raddr.port

            # Skip loopback
            if dest_ip.startswith("127.") or dest_ip == "::1":
                continue

            # Skip standard ports
            if dest_port in STANDARD_PORTS:
                continue

            # Deduplicate within this poll cycle
            key = (dest_ip, dest_port)
            if key in self._seen_connections:
                continue
            self._seen_connections = {k for k in self._seen_connections}  # keep set small
            self._seen_connections.add(key)

            # Add to sliding window
            self._window.add(dest_ip, dest_port)

            # Score this connection
            score, triggers = self._score(dest_ip, dest_port)

            if score > 0:
                try:
                    proc_name = psutil.Process(conn.pid).name() if conn.pid else None
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = None

                suspicious.append({
                    "dest_ip": dest_ip,
                    "dest_port": dest_port,
                    "source_ip": conn.laddr.ip if conn.laddr else socket.gethostname(),
                    "protocol": "TCP" if conn.type == 1 else "UDP",
                    "process_name": proc_name,
                    "rule_score": score,
                    "rule_triggers": triggers,
                })

        # Clear per-poll dedup set
        self._seen_connections.clear()

        for item in suspicious:
            self._process_event(item)

    def _score(self, dest_ip: str, dest_port: int):
        """Apply rule engine to a single connection. Returns (score, triggers)."""
        score = 0
        triggers = []

        # High-risk port list
        if dest_port in HIGH_RISK_PORTS:
            score = max(score, 9)
            triggers.append(f"high_risk_port:{dest_port}")

        # Port scan detection
        unique_ports = len(self._window.unique_dest_ports())
        if unique_ports >= SCAN_PORT_THRESHOLD:
            score = max(score, 8)
            triggers.append(f"port_scan:{unique_ports}_unique_ports")

        # High connection rate
        if self._window.total_count() >= RATE_THRESHOLD:
            score = max(score, 8)
            triggers.append(f"high_rate:{self._window.total_count()}_conns")

        # C2 beacon (repeated to same non-standard port)
        repeats = self._window.connections_to_port(dest_port)
        if repeats >= BEACON_THRESHOLD:
            score = max(score, 7)
            triggers.append(f"c2_beacon:{repeats}x_port_{dest_port}")

        # Low-score catch-all for any non-standard outbound
        if score == 0:
            score = 3
            triggers.append(f"non_std_port:{dest_port}")

        return score, triggers

    def _get_ml_score(self, item: Dict[str, Any]):
        """Call ML service for a network feature vector. Returns (attack_type, risk_score, confidence) or None."""
        if not self.ml_endpoint:
            return None
        try:
            features = {
                "failed_logins": 0,
                "request_rate": self._window.total_count(),
                "commands_count": len(self._window.unique_dest_ports()),
                "sql_payload": 0,
                "honeytoken_access": 0,
                "session_time": POLL_INTERVAL,
                # Extended network features (ignored by old model, used by new)
                "dest_port": item["dest_port"],
                "is_high_risk_port": 1 if item["dest_port"] in HIGH_RISK_PORTS else 0,
                "rule_score": item["rule_score"],
            }
            resp = requests.post(self.ml_endpoint, json=features, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return (
                    data.get("attack_type", "network_anomaly"),
                    int(data.get("risk_score", item["rule_score"])),
                    float(data.get("confidence", 0.7))
                )
        except Exception as e:
            logger.debug(f"ML call failed (using rule score): {e}")
        return None

    def _process_event(self, item: Dict[str, Any]):
        """Optionally enrich with ML, then POST to backend if above threshold."""
        ml_result = self._get_ml_score(item)

        ml_attack_type = None
        ml_risk_score = None
        ml_confidence = None

        if ml_result:
            ml_attack_type, ml_risk_score, ml_confidence = ml_result

        # Effective score: ML takes priority
        effective = ml_risk_score if ml_risk_score is not None else item["rule_score"]

        if effective < RISK_THRESHOLD:
            logger.debug(f"Network event score {effective} below threshold, skipping")
            return

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "source_ip": item["source_ip"],
            "dest_ip": item["dest_ip"],
            "dest_port": item["dest_port"],
            "protocol": item["protocol"],
            "status": "ESTABLISHED",
            "process_name": item.get("process_name"),
            "rule_score": item["rule_score"],
            "rule_triggers": item["rule_triggers"],
            "ml_attack_type": ml_attack_type,
            "ml_risk_score": ml_risk_score,
            "ml_confidence": ml_confidence,
        }

        try:
            resp = requests.post(
                f"{self.backend_url}/api/network-event",
                json=payload,
                headers={
                    "X-Node-API-Key": self.node_api_key,
                    "X-Node-Id": self.node_id,
                },
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                logger.warning(
                    f"🌐 Network event reported — score={effective}, "
                    f"alert_created={data.get('alert_created')}, "
                    f"dest={item['dest_ip']}:{item['dest_port']}"
                )
            else:
                logger.error(f"Backend rejected network event: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Failed to report network event: {e}")
