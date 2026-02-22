"""
File Monitor Module
Monitors honeytoken access using Windows ReadDirectoryChangesW via watchdog
Supports monitoring individual files scattered across multiple directories
"""

import os
import json
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable, List, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)


class HoneytokenEventHandler(FileSystemEventHandler):
    """Handles file system events for honeytoken files"""
    
    def __init__(self, watched_files: Set[str], alert_queue: list, lock: threading.Lock):
        super().__init__()
        self.watched_files = watched_files  # set of absolute lowercase paths
        self.alert_queue = alert_queue
        self.lock = lock
        self._recent_events = {}  # Dedup: filepath -> last_event_time
    
    def _normalize(self, path: str) -> str:
        return os.path.normcase(os.path.abspath(path))
    
    def _is_honeytoken(self, path: str) -> bool:
        return self._normalize(path) in self.watched_files
    
    def _dedup(self, filepath: str, event_type: str) -> bool:
        """Return True if this is a duplicate event (within 5s)"""
        key = f"{filepath}|{event_type}"
        now = time.time()
        with self.lock:
            last = self._recent_events.get(key, 0)
            if now - last < 5:
                return True
            self._recent_events[key] = now
        return False
    
    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self._is_honeytoken(event.src_path) and not self._dedup(event.src_path, 'modified'):
            self._queue_event(event.src_path, 'MODIFIED')
    
    def on_accessed(self, event: FileSystemEvent):
        """Note: watchdog on Windows doesn't fire 'accessed' events directly.
        We handle this in on_modified since opening a file often triggers FILE_NOTIFY_CHANGE_LAST_ACCESS."""
        pass
    
    def on_any_event(self, event: FileSystemEvent):
        """Catch-all: ReadDirectoryChangesW fires FILE_NOTIFY_CHANGE_LAST_ACCESS on file open"""
        if event.is_directory:
            return
        if event.event_type in ('modified', 'created', 'moved'):
            return  # Already handled
        # This catches 'closed' and other events
        if self._is_honeytoken(event.src_path) and not self._dedup(event.src_path, 'accessed'):
            self._queue_event(event.src_path, 'ACCESSED')
    
    def _queue_event(self, filepath: str, action: str):
        event_data = {
            'event': action,
            'filepath': filepath,
            'timestamp': datetime.now().isoformat()
        }
        with self.lock:
            self.alert_queue.append(event_data)
        logger.info(f"🔔 Detected {action}: {os.path.basename(filepath)}")


class FileMonitor:
    """Monitor file access and modifications using watchdog + polling hybrid"""
    
    def __init__(self, watch_dir: str = "system_cache"):
        """Initialize file monitor"""
        self.watch_dir = watch_dir
        self.monitored_files = {}  # filepath -> stats dict
        self.alerts = []
        self.running = False
        self._event_queue = []  # Shared queue from watchdog handlers
        self._lock = threading.Lock()
        self._observer = None
        self._watched_dirs = set()  # Dirs we have observers on
        self._watched_file_set = set()  # Normalized paths for fast lookup
    
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
        Sets up watchdog observers on each parent directory.
        """
        for filepath in file_paths:
            filepath = str(filepath)
            if os.path.exists(filepath):
                try:
                    abs_path = os.path.abspath(filepath)
                    self.monitored_files[abs_path] = {
                        'size': os.path.getsize(abs_path),
                        'modified': os.path.getmtime(abs_path),
                        'accessed': os.path.getatime(abs_path)
                    }
                    self._watched_file_set.add(os.path.normcase(abs_path))
                    logger.info(f"Tracking: {abs_path}")
                except (OSError, PermissionError):
                    logger.warning(f"Cannot access: {filepath}")
            else:
                logger.warning(f"File not found: {filepath}")
        
        logger.info(f"✓ Tracking {len(self.monitored_files)} honeytoken files")
        
        # Start watchdog observers for parent directories
        self._setup_observers()
    
    def _setup_observers(self):
        """Start watchdog observer for each unique parent directory"""
        if self._observer is not None:
            try:
                self._observer.stop()
            except Exception:
                pass
        
        self._observer = Observer()
        handler = HoneytokenEventHandler(self._watched_file_set, self._event_queue, self._lock)
        
        # Get unique parent directories
        parent_dirs = set()
        for filepath in self.monitored_files:
            parent_dirs.add(os.path.dirname(filepath))
        
        for directory in parent_dirs:
            if os.path.exists(directory):
                try:
                    self._observer.schedule(handler, directory, recursive=False)
                    logger.info(f"👁️ Watching directory: {directory}")
                except Exception as e:
                    logger.warning(f"Cannot watch {directory}: {e}")
        
        self._observer.daemon = True
        self._observer.start()
        logger.info(f"✓ Watchdog observer started for {len(parent_dirs)} directories")
    
    def initialize_monitoring(self) -> bool:
        """Initialize monitoring setup"""
        if self.monitored_files:
            logger.info(f"✓ Monitoring {len(self.monitored_files)} individual honeytoken files")
            return True
        
        # Fallback: scan watch_dir if no individual files were added
        if not os.path.exists(self.watch_dir):
            logger.warning(f"⚠ Watch directory not found: {self.watch_dir}")
            return True
        
        logger.info(f"✓ Monitoring directory: {self.watch_dir}")
        
        # Scan initial files
        for root, dirs, files in os.walk(self.watch_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    abs_path = os.path.abspath(filepath)
                    self.monitored_files[abs_path] = {
                        'size': os.path.getsize(abs_path),
                        'modified': os.path.getmtime(abs_path),
                        'accessed': os.path.getatime(abs_path)
                    }
                    self._watched_file_set.add(os.path.normcase(abs_path))
                except (OSError, PermissionError):
                    pass
        
        logger.info(f"✓ Tracking {len(self.monitored_files)} files")
        
        if self.monitored_files:
            self._setup_observers()
        
        return True
    
    def detect_changes(self) -> list:
        """
        Detect file changes using BOTH:
        1. Watchdog event queue (real-time, reliable on Windows)
        2. Stat polling fallback (catches any missed events)
        """
        detected_changes = []
        
        # Method 1: Drain watchdog event queue
        with self._lock:
            while self._event_queue:
                event = self._event_queue.pop(0)
                detected_changes.append(event)
        
        # Method 2: Stat polling fallback (check mtime changes)
        try:
            for filepath, old_stats in list(self.monitored_files.items()):
                try:
                    if not os.path.exists(filepath):
                        # File was deleted — this is suspicious!
                        already_queued = any(c['filepath'] == filepath for c in detected_changes)
                        if not already_queued:
                            detected_changes.append({
                                'event': 'DELETED',
                                'filepath': filepath,
                                'timestamp': datetime.now().isoformat()
                            })
                        del self.monitored_files[filepath]
                        continue
                    
                    current_mtime = os.path.getmtime(filepath)
                    current_size = os.path.getsize(filepath)
                    
                    if current_mtime > old_stats['modified'] or current_size != old_stats['size']:
                        already_queued = any(c['filepath'] == filepath for c in detected_changes)
                        if not already_queued:
                            detected_changes.append({
                                'event': 'MODIFIED',
                                'filepath': filepath,
                                'timestamp': datetime.now().isoformat()
                            })
                        self.monitored_files[filepath] = {
                            'size': current_size,
                            'modified': current_mtime,
                            'accessed': os.path.getatime(filepath)
                        }
                    
                except (OSError, PermissionError):
                    pass
        
        except Exception as e:
            logger.error(f"Error during change detection: {e}")
        
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
        
        Returns:
            List of alerts generated
        """
        changes = self.detect_changes()
        alerts_generated = []
        
        for change in changes:
            alert = self.create_alert(change)
            alerts_generated.append(alert)
            
            # Log alert
            self._print_alert(alert)
            
            # Call callback if provided
            if callback:
                callback(alert)
        
        return alerts_generated
    
    def start_monitoring(self, interval: int = 5, callback: Callable = None):
        """Start continuous monitoring"""
        logger.info(f"👀 Starting continuous monitoring (interval: {interval}s, files: {len(self.monitored_files)})")
        
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
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
    
    def get_alerts(self):
        """Get all recorded alerts"""
        return self.alerts
    
    def _print_alert(self, alert: Dict[str, Any]):
        """Log alert in readable format"""
        logger.warning(f"🚨 ALERT: {alert['severity']} | File: {alert['file_accessed']} | Action: {alert['action']} | User: {alert['username']}@{alert['hostname']}")
    
    def export_alerts(self, filename: str = "alerts.json"):
        """Export alerts to JSON"""
        with open(filename, 'w') as f:
            json.dump(self.alerts, f, indent=2)
        logger.info(f"✓ Exported {len(self.alerts)} alerts to {filename}")


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
