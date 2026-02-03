"""
File Monitor Module
Monitors honeytoken access using watchdog
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable
import time


class FileMonitor:
    """Monitor file access and modifications"""
    
    def __init__(self, watch_dir: str = "system_cache"):
        """Initialize file monitor"""
        self.watch_dir = watch_dir
        self.monitored_files = {}
        self.alerts = []
        self.running = False
    
    def get_system_info(self) -> Dict[str, str]:
        """Get system information"""
        import socket
        try:
            hostname = socket.gethostname()
        except:
            hostname = "unknown"
        
        try:
            username = os.getenv('USERNAME') or os.getenv('USER') or 'unknown'
        except:
            username = 'unknown'
        
        return {
            'hostname': hostname,
            'username': username,
            'platform': os.name
        }
    
    def initialize_monitoring(self) -> bool:
        """Initialize monitoring setup"""
        if not os.path.exists(self.watch_dir):
            print(f"✗ Watch directory not found: {self.watch_dir}")
            return False
        
        print(f"✓ Monitoring directory: {self.watch_dir}")
        
        # Scan initial files
        for root, dirs, files in os.walk(self.watch_dir):
            for file in files:
                filepath = os.path.join(root, file)
                self.monitored_files[filepath] = {
                    'size': os.path.getsize(filepath),
                    'modified': os.path.getmtime(filepath),
                    'accessed': os.path.getatime(filepath)
                }
        
        print(f"✓ Tracking {len(self.monitored_files)} files")
        return True
    
    def detect_changes(self) -> list:
        """Detect file changes using polling"""
        detected_changes = []
        
        try:
            for root, dirs, files in os.walk(self.watch_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    
                    try:
                        current_stats = {
                            'size': os.path.getsize(filepath),
                            'modified': os.path.getmtime(filepath),
                            'accessed': os.path.getatime(filepath)
                        }
                        
                        # Check if file is new
                        if filepath not in self.monitored_files:
                            detected_changes.append({
                                'event': 'created',
                                'filepath': filepath,
                                'timestamp': datetime.now().isoformat()
                            })
                            self.monitored_files[filepath] = current_stats
                        else:
                            old_stats = self.monitored_files[filepath]
                            
                            # Check for modifications
                            if current_stats['modified'] > old_stats['modified']:
                                detected_changes.append({
                                    'event': 'modified',
                                    'filepath': filepath,
                                    'timestamp': datetime.now().isoformat()
                                })
                                self.monitored_files[filepath] = current_stats
                            
                            # Check for access (file opened)
                            if current_stats['accessed'] > old_stats['accessed']:
                                # Avoid duplicate access events
                                last_alert = self.alerts[-1] if self.alerts else None
                                if not last_alert or last_alert['filepath'] != filepath or \
                                   (datetime.fromisoformat(datetime.now().isoformat()) - 
                                    datetime.fromisoformat(last_alert['timestamp'])).seconds > 5:
                                    
                                    detected_changes.append({
                                        'event': 'accessed',
                                        'filepath': filepath,
                                        'timestamp': datetime.now().isoformat()
                                    })
                    
                    except (OSError, PermissionError):
                        # File may be locked or deleted
                        pass
        
        except Exception as e:
            print(f"Error during change detection: {e}")
        
        return detected_changes
    
    def create_alert(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Create alert from detected event"""
        sys_info = self.get_system_info()
        
        alert = {
            'timestamp': event['timestamp'],
            'hostname': sys_info['hostname'],
            'username': sys_info['username'],
            'file_accessed': os.path.basename(event['filepath']),
            'file_path': event['filepath'],
            'action': event['event'].upper(),
            'severity': self._calculate_severity(event['filepath']),
            'alert_type': 'HONEYTOKEN_ACCESS'
        }
        
        self.alerts.append(alert)
        return alert
    
    def _calculate_severity(self, filepath: str) -> str:
        """Calculate severity level based on file type"""
        filename = os.path.basename(filepath).lower()
        
        if any(x in filename for x in ['key', 'password', 'credential', 'aws']):
            return 'CRITICAL'
        elif any(x in filename for x in ['salary', 'financial', 'backup', 'sql']):
            return 'HIGH'
        elif any(x in filename for x in ['env', 'config', 'api']):
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def monitor_once(self, callback: Callable = None) -> list:
        """
        Perform one monitoring cycle
        
        Args:
            callback: Function to call for each alert (for integration with sender)
        
        Returns:
            List of alerts generated
        """
        changes = self.detect_changes()
        alerts_generated = []
        
        for change in changes:
            alert = self.create_alert(change)
            alerts_generated.append(alert)
            
            # Print alert
            self._print_alert(alert)
            
            # Call callback if provided
            if callback:
                callback(alert)
        
        return alerts_generated
    
    def start_monitoring(self, interval: int = 5, callback: Callable = None):
        """
        Start continuous monitoring
        
        Args:
            interval: Check interval in seconds
            callback: Function to call for each alert
        """
        self.running = True
        print(f"\n🔍 Starting file monitor (checking every {interval}s)...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while self.running:
                self.monitor_once(callback)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n✓ Monitor stopped")
            self.running = False
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
    
    def get_alerts(self) -> list:
        """Get all recorded alerts"""
        return self.alerts
    
    def _print_alert(self, alert: Dict[str, Any]):
        """Print alert in readable format"""
        print(f"\n🚨 ALERT DETECTED")
        print(f"   File: {alert['file_accessed']}")
        print(f"   Action: {alert['action']}")
        print(f"   User: {alert['username']}@{alert['hostname']}")
        print(f"   Severity: {alert['severity']}")
        print(f"   Time: {alert['timestamp']}")
    
    def export_alerts(self, filename: str = "alerts.json"):
        """Export alerts to JSON"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.alerts, f, indent=2)
            print(f"\n✓ Alerts exported to {filename}")
        except Exception as e:
            print(f"✗ Error exporting alerts: {e}")


def main():
    """Main monitoring function"""
    monitor = FileMonitor()
    
    if monitor.initialize_monitoring():
        # Run one monitoring cycle
        alerts = monitor.monitor_once()
        
        if alerts:
            print(f"\n✓ Detected {len(alerts)} changes")
            monitor.export_alerts()
        else:
            print("\n✓ No changes detected")


if __name__ == '__main__':
    main()
