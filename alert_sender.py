"""
Alert Sender Module
Sends detected alerts to backend API
"""

import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime


class AlertSender:
    """Send alerts to backend API"""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """Initialize alert sender"""
        self.api_url = api_url.rstrip('/')
        self.alert_endpoint = f"{self.api_url}/predict"
        self.alerts_sent = 0
        self.alerts_failed = 0
    
    def check_api_health(self) -> bool:
        """Check if backend API is available"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=2)
            if response.status_code == 200:
                print(f"✓ Backend API is healthy")
                return True
        except requests.exceptions.RequestException:
            print(f"✗ Backend API not responding at {self.api_url}")
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
        Send alert to backend API
        
        Args:
            alert: Alert dictionary from file monitor
        
        Returns:
            True if sent successfully
        """
        try:
            # Convert alert to ML input format
            log_data = self.alert_to_log_format(alert)
            
            print(f"\n📤 Sending alert to API...")
            print(f"   File: {alert['file_accessed']}")
            print(f"   Action: {alert['action']}")
            
            # Send to backend API
            response = requests.post(
                self.alert_endpoint,
                json=log_data,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"\n✓ Alert processed by ML model")
                print(f"   Attack Type: {result['attack_type']}")
                print(f"   Risk Score: {result['risk_score']}/10")
                print(f"   Confidence: {result['confidence']:.2%}")
                print(f"   Anomaly: {result['is_anomaly']}")
                
                self.alerts_sent += 1
                
                # Store full response
                alert['ml_prediction'] = result
                alert['backend_status'] = 'SUCCESS'
                
                return True
            else:
                print(f"✗ API returned status {response.status_code}")
                print(f"   Response: {response.text}")
                alert['backend_status'] = f'ERROR_{response.status_code}'
                self.alerts_failed += 1
                return False
        
        except requests.exceptions.Timeout:
            print(f"✗ API request timed out")
            alert['backend_status'] = 'TIMEOUT'
            self.alerts_failed += 1
            return False
        except requests.exceptions.ConnectionError:
            print(f"✗ Cannot connect to API at {self.alert_endpoint}")
            print(f"   Make sure backend is running: python ml_api.py")
            alert['backend_status'] = 'NO_CONNECTION'
            self.alerts_failed += 1
            return False
        except Exception as e:
            print(f"✗ Error sending alert: {e}")
            alert['backend_status'] = f'ERROR_{type(e).__name__}'
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
