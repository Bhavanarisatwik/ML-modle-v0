"""
Alert Sender Module
Sends detected alerts to backend API
"""

import requests
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertSender:
    """Send alerts to backend API"""
    
    def __init__(self, api_url: str = "https://ml-modle-v0-1.onrender.com",
                 node_id: str = None, node_api_key: str = None):
        """Initialize alert sender with node authentication"""
        # Remove /api suffix if present - we'll add endpoints ourselves
        self.api_url = api_url.rstrip('/').replace('/api', '')
        self.alert_endpoint = f"{self.api_url}/api/agent-alert"
        self.node_id = node_id
        self.node_api_key = node_api_key
        self.alerts_sent = 0
        self.alerts_failed = 0
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with node authentication"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.node_id:
            headers["X-Node-Id"] = self.node_id
        if self.node_api_key:
            headers["X-Node-Key"] = self.node_api_key
            headers["X-Node-API-Key"] = self.node_api_key
        return headers
    
    def check_api_health(self) -> bool:
        """Check if backend API is available"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=5)
            if response.status_code == 200:
                logger.info(f"✓ Backend API is healthy at {self.api_url}")
                return True
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Backend API not responding at {self.api_url}: {e}")
            return False
        return False
    
    def alert_to_log_format(self, alert: Dict[str, Any]) -> Dict[str, int]:
        """
        Convert honeytoken alert to security log format for ML model
        
        Maps:
        - file access → failed_logins (higher = more suspicious)
        - action severity → request_rate (unusual patterns)
        - file type → sql_payload detection
        - access method → honeytoken_access flag
        """
        
        action = alert['action'].upper()
        severity = alert['severity']
        filename = alert['file_accessed'].lower()
        
        # Determine suspicious login attempts
        if 'ACCESSED' in action:
            failed_logins = 90  # High - accessing hidden files
        elif 'MODIFIED' in action:
            failed_logins = 110  # Very high - modifying files
        else:
            failed_logins = 50
        
        # Request rate based on severity
        severity_map = {
            'CRITICAL': 550,
            'HIGH': 450,
            'MEDIUM': 250,
            'LOW': 100
        }
        request_rate = severity_map.get(severity, 200)
        
        # Commands count based on file type
        if any(x in filename for x in ['backup', 'sql', 'database']):
            commands_count = 15
        else:
            commands_count = 8
        
        # SQL payload detection
        sql_payload = 1 if 'sql' in filename or 'backup' in filename else 0
        
        # Honeytoken access flag
        honeytoken_access = 1  # Always 1 for honeytoken access
        
        # Session time (how long they spent)
        session_time = 300
        
        return {
            'failed_logins': failed_logins,
            'request_rate': request_rate,
            'commands_count': commands_count,
            'sql_payload': sql_payload,
            'honeytoken_access': honeytoken_access,
            'session_time': session_time
        }
    
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Send alert to backend API in AgentEvent format.
        Includes X-Node-Id and X-Node-Key headers for authentication.
        """
        try:
            file_accessed = alert.get('file_accessed', alert.get('filepath', 'unknown'))
            action = alert.get('action', 'ACCESSED')
            
            logger.info(f"📤 Sending alert: {file_accessed} ({action}) -> {self.alert_endpoint}")
            
            # Build AgentEvent-compatible payload
            import platform
            import os
            payload = {
                "timestamp": alert.get('timestamp', datetime.now().isoformat()),
                "hostname": alert.get('hostname', platform.node()),
                "username": alert.get('username', os.getenv('USERNAME', os.getenv('USER', 'unknown'))),
                "file_accessed": os.path.basename(file_accessed),
                "file_path": alert.get('file_path', alert.get('filepath', file_accessed)),
                "action": action.upper(),
                "severity": alert.get('severity', 'HIGH'),
                "alert_type": alert.get('alert_type', 'HONEYTOKEN_ACCESS'),
            }

            # Include process metadata if captured by file_monitor
            for field in ('process_name', 'pid', 'process_user', 'cmdline'):
                if alert.get(field) is not None:
                    payload[field] = alert[field]
            
            # Send with node auth headers
            response = requests.post(
                self.alert_endpoint,
                json=payload,
                headers=self._get_headers(),
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                ml = result.get('ml_prediction')
                if ml:
                    logger.info(f"✓ Alert processed: {ml.get('attack_type')} risk={ml.get('risk_score')}/10 conf={ml.get('confidence', 0):.0%}")
                else:
                    logger.info(f"✓ Alert saved (no ML data returned)")
                
                self.alerts_sent += 1
                return True
            else:
                logger.error(f"✗ API returned {response.status_code}: {response.text[:200]}")
                self.alerts_failed += 1
                return False
        
        except requests.exceptions.Timeout:
            logger.error(f"✗ API request timed out -> {self.alert_endpoint}")
            self.alerts_failed += 1
            return False
        except requests.exceptions.ConnectionError:
            logger.error(f"✗ Cannot connect to API at {self.alert_endpoint}")
            self.alerts_failed += 1
            return False
        except Exception as e:
            logger.error(f"✗ Error sending alert: {e}")
            self.alerts_failed += 1
            return False
    
    def send_batch_alerts(self, alerts: list) -> Dict[str, int]:
        """
        Send multiple alerts
        
        Args:
            alerts: List of alert dictionaries
        
        Returns:
            Dictionary with success/failure counts
        """
        results = {
            'total': len(alerts),
            'success': 0,
            'failed': 0
        }
        
        for alert in alerts:
            if self.send_alert(alert):
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get sender statistics"""
        return {
            'total_sent': self.alerts_sent,
            'total_failed': self.alerts_failed,
            'success_rate': (self.alerts_sent / (self.alerts_sent + self.alerts_failed) * 100) 
                           if (self.alerts_sent + self.alerts_failed) > 0 else 0
        }
    
    def print_statistics(self):
        """Print sender statistics"""
        stats = self.get_statistics()
        print(f"\n" + "="*60)
        print("📊 ALERT SENDER STATISTICS")
        print("="*60)
        print(f"Total Sent: {stats['total_sent']}")
        print(f"Total Failed: {stats['total_failed']}")
        print(f"Success Rate: {stats['success_rate']:.1f}%")
        print("="*60)


def test_alert_sender():
    """Test the alert sender with sample alert"""
    
    # Create sample alert (what file monitor would detect)
    sample_alert = {
        'timestamp': datetime.now().isoformat(),
        'hostname': 'ATTACKER-PC',
        'username': 'attacker',
        'file_accessed': 'aws_keys.txt',
        'file_path': 'system_cache/aws_keys.txt',
        'action': 'ACCESSED',
        'severity': 'CRITICAL',
        'alert_type': 'HONEYTOKEN_ACCESS'
    }
    
    print("="*60)
    print("🧪 TESTING ALERT SENDER")
    print("="*60)
    
    sender = AlertSender()
    
    # Check API health
    if not sender.check_api_health():
        print("\n⚠️  Backend API is not running")
        print("Start it with: python ml_api.py")
        return
    
    # Send sample alert
    print("\nSending sample honeytoken alert...")
    sender.send_alert(sample_alert)
    
    # Print statistics
    sender.print_statistics()


if __name__ == '__main__':
    test_alert_sender()
