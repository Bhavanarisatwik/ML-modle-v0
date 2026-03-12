"""
DecoyVerse Packet Monitor
=========================
Optional inbound scan detection using Scapy (requires admin/root + scapy).

Detects inbound reconnaissance from an attacker scanning this machine:
  - SYN scan  (nmap -sS): ≥10 unique dest ports from same source in 60s
  - NULL scan (nmap -sN): TCP packet with no flags
  - FIN scan  (nmap -sF): TCP packet with only FIN flag
  - Xmas scan (nmap -sX): TCP FIN + PSH + URG flags
  - UDP scan  (nmap -sU): ≥10 unique dest ports from same source in 60s

Graceful degradation:
  - If scapy not installed  → logs warning, does nothing (agent continues fine)
  - If no admin/root rights → logs warning, does nothing (agent continues fine)
  - Never raises exceptions into the parent agent

Usage (agent.py):
    from packet_monitor import PacketMonitor
    pm = PacketMonitor(backend_url, node_id, node_api_key)
    pm.start()   # starts as a daemon thread; returns immediately
"""

import threading
import logging
import requests
from datetime import datetime
from collections import defaultdict, deque
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Detection thresholds ──────────────────────────────────────────────────────
WINDOW_SECONDS = 60        # sliding window for scan counting
SYN_SCAN_THRESHOLD = 10    # unique dest ports from same source → SYN scan
UDP_SCAN_THRESHOLD = 10    # unique dest ports from same source → UDP scan
ALERT_COOLDOWN = 120       # seconds before re-alerting same source+type


class PacketMonitor:
    """
    Daemon thread that sniffs raw packets and detects inbound port scans /
    nmap probes targeted at this machine.

    Requires:
      - scapy   (pip install scapy)
      - Admin / root privileges (raw socket access)
    """

    def __init__(self, backend_url: str, node_id: str, node_api_key: str):
        self.backend_url = backend_url.rstrip("/")
        self.node_id = node_id
        self.node_api_key = node_api_key

        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Sliding windows: src_ip → deque of (epoch_float, dest_port)
        self._syn_window: Dict[str, deque] = defaultdict(deque)
        self._udp_window: Dict[str, deque] = defaultdict(deque)

        # Cooldown tracker: "{src_ip}:{scan_type}" → last alert epoch
        self._alerted: Dict[str, float] = {}

    # ── Public interface ──────────────────────────────────────────────────────

    def start(self):
        """
        Start packet monitoring in the background.
        Silently skips if scapy is missing or privileges are insufficient.
        """
        try:
            import scapy.all  # noqa: F401  (just checking import works)
        except ImportError:
            logger.warning(
                "📦 scapy not installed — inbound scan detection disabled. "
                "Install with: pip install scapy"
            )
            return

        if not self._can_sniff():
            logger.warning(
                "🔒 Inbound scan detection requires admin/root privileges. "
                "Re-run the agent as Administrator (Windows) or root/sudo (Linux/macOS) "
                "to enable nmap / port-scan detection."
            )
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="dv-packet-monitor"
        )
        self._thread.start()
        logger.info("🛡️  Packet monitor started — inbound scan detection active")

    def stop(self):
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _can_sniff() -> bool:
        """Return True if we can open a raw socket (indicates admin/root)."""
        import socket as _socket
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_RAW, _socket.IPPROTO_TCP)
            s.close()
            return True
        except (PermissionError, OSError):
            return False

    def _run(self):
        """Main sniff loop — blocks inside scapy.sniff(); runs in daemon thread."""
        try:
            from scapy.all import sniff
            sniff(
                filter="tcp or udp",
                prn=self._packet_callback,
                store=False,
                stop_filter=lambda _: not self._running,
            )
        except Exception as e:
            logger.error(f"Packet monitor fatal error: {e}")

    def _packet_callback(self, pkt):
        """Route each captured packet to the TCP or UDP handler."""
        try:
            from scapy.layers.inet import IP, TCP, UDP
            if IP not in pkt:
                return
            src_ip: str = pkt[IP].src
            # Ignore loopback / link-local traffic
            if src_ip.startswith("127.") or src_ip == "::1":
                return
            if TCP in pkt:
                self._handle_tcp(src_ip, pkt)
            elif UDP in pkt:
                self._handle_udp(src_ip, pkt)
        except Exception as e:
            logger.debug(f"Packet callback error (non-fatal): {e}")

    def _handle_tcp(self, src_ip: str, pkt):
        """Detect NULL, FIN, Xmas, and SYN scans."""
        from scapy.layers.inet import TCP
        tcp = pkt[TCP]
        dst_port: int = tcp.dport
        flags = int(tcp.flags)

        # ── NULL scan: zero flags ──────────────────────────────────────────
        if flags == 0:
            self._fire_alert(src_ip, "null_scan", 8, {
                "dest_port": dst_port,
                "detail": "TCP NULL packet (flags=0) — nmap -sN",
            })
            return

        FIN = 0x001
        SYN = 0x002
        ACK = 0x010
        PSH = 0x008
        URG = 0x020

        # ── FIN scan: only FIN ────────────────────────────────────────────
        if flags == FIN:
            self._fire_alert(src_ip, "fin_scan", 8, {
                "dest_port": dst_port,
                "detail": "TCP FIN-only packet — nmap -sF",
            })
            return

        # ── Xmas scan: FIN + PSH + URG ────────────────────────────────────
        if (flags & FIN) and (flags & PSH) and (flags & URG):
            self._fire_alert(src_ip, "xmas_scan", 8, {
                "dest_port": dst_port,
                "detail": "TCP Xmas packet (FIN+PSH+URG) — nmap -sX",
            })
            return

        # ── SYN scan: SYN without ACK → track sliding window ─────────────
        if (flags & SYN) and not (flags & ACK):
            now = datetime.utcnow().timestamp()
            self._add_to_window(self._syn_window, src_ip, dst_port, now)
            unique = self._count_unique_ports(self._syn_window, src_ip, now)
            if unique >= SYN_SCAN_THRESHOLD:
                self._fire_alert(src_ip, "syn_scan", 9, {
                    "unique_ports_scanned": unique,
                    "detail": (
                        f"SYN scan: {unique} unique ports in {WINDOW_SECONDS}s — nmap -sS"
                    ),
                })

    def _handle_udp(self, src_ip: str, pkt):
        """Detect UDP port scans."""
        from scapy.layers.inet import UDP
        dst_port: int = pkt[UDP].dport
        now = datetime.utcnow().timestamp()
        self._add_to_window(self._udp_window, src_ip, dst_port, now)
        unique = self._count_unique_ports(self._udp_window, src_ip, now)
        if unique >= UDP_SCAN_THRESHOLD:
            self._fire_alert(src_ip, "udp_scan", 7, {
                "unique_ports_scanned": unique,
                "detail": (
                    f"UDP scan: {unique} unique ports in {WINDOW_SECONDS}s — nmap -sU"
                ),
            })

    # ── Window helpers ────────────────────────────────────────────────────────

    def _add_to_window(
        self, window: Dict[str, deque], src_ip: str, dst_port: int, now: float
    ):
        q = window[src_ip]
        q.append((now, dst_port))
        cutoff = now - WINDOW_SECONDS
        while q and q[0][0] < cutoff:
            q.popleft()

    def _count_unique_ports(
        self, window: Dict[str, deque], src_ip: str, now: float
    ) -> int:
        cutoff = now - WINDOW_SECONDS
        return len({p for ts, p in window.get(src_ip, []) if ts >= cutoff})

    # ── Alert dispatch ────────────────────────────────────────────────────────

    def _fire_alert(self, src_ip: str, scan_type: str, score: int, details: dict):
        """
        Post a network-event alert to the backend.
        Respects ALERT_COOLDOWN to avoid flooding for sustained scans.
        """
        cooldown_key = f"{src_ip}:{scan_type}"
        now = datetime.utcnow().timestamp()

        last = self._alerted.get(cooldown_key, 0.0)
        if now - last < ALERT_COOLDOWN:
            return
        self._alerted[cooldown_key] = now

        logger.warning(
            f"🚨 Inbound scan detected — type={scan_type}, src={src_ip}, score={score}/10"
        )

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "source_ip": src_ip,
            "dest_ip": "0.0.0.0",
            "dest_port": details.get("dest_port", 0),
            "protocol": "UDP" if scan_type == "udp_scan" else "TCP",
            "status": "SCAN_DETECTED",
            "process_name": None,
            "rule_score": score,
            "rule_triggers": [scan_type],
            "ml_attack_type": "Recon",
            "ml_risk_score": score,
            "ml_confidence": 0.9,
        }

        try:
            resp = requests.post(
                f"{self.backend_url}/api/network-event",
                json=payload,
                headers={
                    "X-Node-API-Key": self.node_api_key,
                    "X-Node-Id": self.node_id,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(f"✅ Packet alert posted — {scan_type} from {src_ip}")
            else:
                logger.error(
                    f"Backend rejected packet alert: {resp.status_code} {resp.text[:200]}"
                )
        except Exception as e:
            logger.error(f"Failed to post packet alert to backend: {e}")
