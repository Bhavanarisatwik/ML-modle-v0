"""
Zeek `conn.log` TSV parser and simulator.
Reads from a conn.log file in real-time.
"""

import os
import time
import requests
import json
from pathlib import Path
from typing import Dict, List, Any

class ZeekNetworkMonitor:
    def __init__(self, log_path: str = "conn.log", api_url: str = None):
        """Initialize Zeek log tailer"""
        self.log_path = Path(log_path)
        self.api_url = api_url
        self.last_pos = 0
        self.batch_size = 50
        
    def initialize_monitoring(self) -> bool:
        """Create a mock conn.log if it doesn't exist to avoid crashing"""
        if not self.log_path.exists():
            print(f"   [Zeek] Creating dummy {self.log_path} for testing..")
            with open(self.log_path, 'w', encoding='utf-8') as f:
                f.write("#separator \\x09\n")
                f.write("#set_separator	,\n")
                f.write("#empty_field	(empty)\n")
                f.write("#unset_field	-\n")
                f.write("#path	conn\n")
                f.write("#fields	ts	uid	id.orig_h	id.orig_p	id.resp_h	id.resp_p	proto	service	duration	orig_bytes	resp_bytes	conn_state	local_orig	local_resp	missed_bytes	history	orig_pkts	orig_ip_bytes	resp_pkts	resp_ip_bytes	tunnel_parents\n")
                f.write("#types	time	string	addr	port	addr	port	enum	string	interval	count	count	string	bool	bool	count	string	count	count	count	count	set[string]\n")
        
        # Seek to the end currently
        self.last_pos = self.log_path.stat().st_size
        return True

    def process_new_lines(self) -> List[Dict[str, Any]]:
        """Tail the conn.log and parse TSV lines into network flows"""
        if not self.log_path.exists():
            return []
            
        current_size = self.log_path.stat().st_size
        if current_size < self.last_pos:
            # File rotated
            self.last_pos = 0
            
        if current_size == self.last_pos:
            # No new lines
            return []
            
        flows = []
        with open(self.log_path, 'r', encoding='utf-8') as f:
            f.seek(self.last_pos)
            for line in f:
                line = line.strip()
                # Skip Zeek headers
                if not line or line.startswith('#'):
                    continue
                    
                parts = line.split('\t')
                
                # Minimum standard Zeek conn.log has 21 fields. If not, skip.
                if len(parts) < 21:
                    continue
                    
                # Index mapping based on standard header
                try:
                    duration = float(parts[8]) if parts[8] != '-' else 0.0
                    orig_bytes = float(parts[9]) if parts[9] != '-' else 0.0
                    resp_bytes = float(parts[10]) if parts[10] != '-' else 0.0
                    orig_pkts = int(parts[16]) if parts[16] != '-' else 0
                    resp_pkts = int(parts[18]) if parts[18] != '-' else 0
                    
                    dst_port = int(parts[5]) if parts[5] != '-' else 0
                    protocol_str = parts[6]
                    protocol = 6 if protocol_str == 'tcp' else 17 if protocol_str == 'udp' else 0
                    
                    if duration <= 0:
                        continue # Skip 0-duration flows as rates hit infinity
                        
                    flow_bytes_s = (orig_bytes + resp_bytes) / duration
                    flow_pkts_s = (orig_pkts + resp_pkts) / duration
                    
                    flow = {
                        "duration": duration,
                        "orig_pkts": orig_pkts,
                        "resp_pkts": resp_pkts,
                        "orig_bytes": orig_bytes,
                        "resp_bytes": resp_bytes,
                        "flow_bytes_s": flow_bytes_s,
                        "flow_pkts_s": flow_pkts_s,
                        "dst_port": dst_port,
                        "protocol": protocol,
                        
                        # Extra metadata for alerting
                        "_src_ip": parts[2],
                        "_dst_ip": parts[4]
                    }
                    flows.append(flow)
                    
                except ValueError:
                    continue
                    
            self.last_pos = f.tell()
            
        return flows
        
    def send_to_api_and_alert(self, flows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Send valid flows to ML backend and return any generated alerts"""
        alerts = []
        if not flows or not self.api_url:
            return alerts
            
        # Clean out meta fields starting with _ for API request
        api_flows = []
        for f in flows:
            api_f = {k: v for k, v in f.items() if not k.startswith('_')}
            api_flows.append(api_f)
            
        endpoint = f"{self.api_url.rstrip('/')}/predict/network"
        
        try:
            resp = requests.post(endpoint, json={"flows": api_flows}, timeout=3)
            if resp.status_code == 200:
                predictions = resp.json().get('predictions', [])
                
                for idx, pred in enumerate(predictions):
                    label = pred.get('label')
                    confidence = pred.get('confidence', 0.0)
                    
                    if label != "BENIGN" and confidence > 0.85:
                        orig_flow = flows[idx]
                        
                        # Generate alert payload format
                        alert = {
                            "type": "Network Intrusion",
                            "severity": "CRITICAL" if confidence > 0.95 else "HIGH",
                            "message": f"Network anomaly detected: {label} (Confidence: {confidence:.2f})",
                            "action": label,
                            "file_accessed": f"Port: {orig_flow.get('_dst_ip')}:{orig_flow.get('dst_port')}",
                            "username": orig_flow.get('_src_ip', 'Unknown SRC'),
                            "path": "conn.log"
                        }
                        alerts.append(alert)
        except Exception as e:
            pass # Silently fail on API timeout 
            
        return alerts

def simulate_zeek_ddos():
    """Helper mock to append a DDoS Zeek log signature to conn.log"""
    time.sleep(10)
    print("\n   [Simulator] Injecting mock DDoS TCP syn flood to conn.log...")
    with open('conn.log', 'a', encoding='utf-8') as f:
        # Example high pkts/s, fast duration, matching a flood profile
        f.write("1612345678.000000\tCZeekUid\t10.0.0.5\t54321\t192.168.1.100\t80\ttcp\thttp\t0.05\t5000\t100\tS1\t-\t-\t0\tS\t150\t8000\t2\t120\t(empty)\n")

