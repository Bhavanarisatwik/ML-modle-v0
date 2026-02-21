"""
File Monitor Module
Monitors honeytoken access using file stat polling
Supports monitoring individual files scattered across multiple directories
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable, List


class FileMonitor:
    """Monitor file access and modifications"""
    
    def __init__(self, watch_dir: str = "system_cache"):
        """Initialize file monitor"""
        self.watch_dir = watch_dir
        self.monitored_files = {}
        self.alerts = []
        self.running = False
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        import platform
        
        try:
            hostname = platform.node()
            username = os.getenv('USERNAME', os.getenv('USER', 'unknown'))
            
            return {
                'hostname': hostname,
                'username': username,
                'os': platform.system(),
                'os_version': platform.version(),
                'machine': platform.machine()
            }
        except Exception:
            return {
                'hostname': 'unknown',
                'username': 'unknown',
                'os': 'unknown'
            }
    
    def add_files(self, file_paths: List[str]):
        """
        Add specific file paths to monitor.
        Use this to track honeytokens deployed to scattered locations.
        """
        for filepath in file_paths:
            filepath = str(filepath)
            if os.path.exists(filepath):
                try:
                    self.monitored_files[filepath] = {
                        'size': os.path.getsize(filepath),
                        'modified': os.path.getmtime(filepath),
                        'accessed': os.path.getatime(filepath)
                    }
                except (OSError, PermissionError):
                    pass
        
        if self.monitored_files:
            print(f"✓ Tracking {len(self.monitored_files)} honeytoken files")
    
    def initialize_monitoring(self) -> bool:
        """Initialize monitoring setup"""
        # If we already have individually added files, we're good
        if self.monitored_files:
            print(f"✓ Monitoring {len(self.monitored_files)} individual honeytoken files")
            return True
        
        # Fallback: scan watch_dir if no individual files were added
        if not os.path.exists(self.watch_dir):
            print(f"⚠ Watch directory not found: {self.watch_dir}")
            # Not a fatal error if we have no files - agent will still function
            return True
        
        print(f"✓ Monitoring directory: {self.watch_dir}")
        
        # Scan initial files
        for root, dirs, files in os.walk(self.watch_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    self.monitored_files[filepath] = {
                        'size': os.path.getsize(filepath),
                        'modified': os.path.getmtime(filepath),
                        'accessed': os.path.getatime(filepath)
                    }
                except (OSError, PermissionError):
                    pass
        
        print(f"✓ Tracking {len(self.monitored_files)} files")
        return True
    
    def detect_changes(self) -> list:
        """Detect file changes using polling across all monitored files"""
        detected_changes = []
        
        try:
            # Check each monitored file (works for files in any directory)
            for filepath, old_stats in list(self.monitored_files.items()):
                try:
                    if not os.path.exists(filepath):
                        # File was deleted
                        detected_changes.append({
                            'event': 'deleted',
                            'filepath': filepath,
                            'timestamp': datetime.now().isoformat()
                        })
                        del self.monitored_files[filepath]
                        continue
                    
                    current_stats = {
                        'size': os.path.getsize(filepath),
                        'modified': os.path.getmtime(filepath),
                        'accessed': os.path.getatime(filepath)
                    }
                    
                    # Check for modifications
                    if current_stats['modified'] > old_stats['modified']:
                        detected_changes.append({
                            'event': 'modified',
                            'filepath': filepath,
                            'timestamp': datetime.now().isoformat()
                        })
                        self.monitored_files[filepath] = current_stats
                    
                    # Check for access (file opened)
                    elif current_stats['accessed'] > old_stats['accessed']:
                        # Avoid duplicate access events within 5 seconds
                        last_alert = self.alerts[-1] if self.alerts else None
                        if not last_alert or last_alert.get('filepath') != filepath or \
                           (datetime.fromisoformat(datetime.now().isoformat()) - 
                            datetime.fromisoformat(last_alert['timestamp'])).seconds > 5:
                            
                            detected_changes.append({
                                'event': 'accessed',
                                'filepath': filepath,
                                'timestamp': datetime.now().isoformat()
                            })
                            self.monitored_files[filepath] = current_stats
                    
                except (OSError, PermissionError):
                    # File may be locked or deleted
                    pass
        
        except Exception as e:
            print(f"Error during change detection: {e}")
        
        return detected_changes
    
    def create_alert(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Create alert from detected event"""
        system_info = self.get_system_info()
        filepath = event['filepath']
        
        alert = {
            'timestamp': event['timestamp'],
            'hostname': system_info['hostname'],
            'username': system_info['username'],
            'file_accessed': os.path.basename(filepath),
            'file_path': filepath,
            'filepath': filepath,
            'action': event['event'].upper(),
            'severity': self._calculate_severity(filepath),
            'alert_type': 'HONEYTOKEN_ACCESS'
        }
        
        self.alerts.append(alert)
        return alert
    
    def _calculate_severity(self, filepath: str) -> str:
        """Calculate severity level based on file type"""
        filename = os.path.basename(filepath).lower()
        
        # Critical: credential files
        if any(x in filename for x in ['aws', 'credentials', 'password', 'secret', 'token', 'key', 'id_rsa', 'id_ed25519']):
            return 'CRITICAL'
        # High: database and config files
        if any(x in filename for x in ['database', 'db_', 'mysql', 'postgres', 'mongodb', 'kubeconfig', '.env']):
            return 'HIGH'
        # Medium: other sensitive files
        if any(x in filename for x in ['backup', 'config', 'ssh', '.pem']):
            return 'MEDIUM'
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
        import time
        
        print(f"\n👀 Starting continuous monitoring (interval: {interval}s)")
        print(f"   Watching {len(self.monitored_files)} files")
        
        self.running = True
        try:
            while self.running:
                self.monitor_once(callback)
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stop_monitoring()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
    
    def get_alerts(self):
        """Get all recorded alerts"""
        return self.alerts
    
    def _print_alert(self, alert: Dict[str, Any]):
        """Print alert in readable format"""
        print(f"\n🚨 ALERT: {alert['severity']}")
        print(f"   File: {alert['file_accessed']}")
        print(f"   Path: {alert['file_path']}")
        print(f"   Action: {alert['action']}")
        print(f"   User: {alert['username']}@{alert['hostname']}")
        print(f"   Time: {alert['timestamp']}")
    
    def export_alerts(self, filename: str = "alerts.json"):
        """Export alerts to JSON"""
        with open(filename, 'w') as f:
            json.dump(self.alerts, f, indent=2)
        print(f"\n✓ Exported {len(self.alerts)} alerts to {filename}")


def main():
    """Main monitoring function"""
    print("="*60)
    print("🔍 FILE MONITOR - Honeytoken Access Detector")
    print("="*60)
    
    monitor = FileMonitor()
    monitor.initialize_monitoring()
    
    print("\n💡 Watching for file access events...")
    print("   Press Ctrl+C to stop\n")
    
    monitor.start_monitoring(interval=3)


if __name__ == '__main__':
    main()
