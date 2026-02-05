"""
Main Agent Module
Orchestrates honeytoken deployment, monitoring, and alerting
"""

import os
import sys
import time
from agent_setup import HoneytokenSetup
from file_monitor import FileMonitor
from alert_sender import AlertSender
from agent_config import AgentConfig, AgentRegistration, ensure_agent_registered


class DeceptionAgent:
    """Endpoint deception agent with honeytokens"""
    
    def __init__(self, watch_dir: str = "system_cache"):
        """Initialize the deception agent"""
        self.watch_dir = watch_dir
        self.config = AgentConfig()
        self.setup = HoneytokenSetup(watch_dir)
        self.monitor = FileMonitor(watch_dir)
        # Use ML service URL for alert scoring
        ml_service_url = self.config.get_ml_service_url()
        self.sender = AlertSender(api_url=ml_service_url)
        self.registration = AgentRegistration(self.config)
        self.running = False
    
    def setup_honeytokens(self) -> bool:
        """Setup honeytokens based on deployment config"""
        print("\n" + "="*70)
        print("🍯 PHASE 1: HONEYTOKEN DEPLOYMENT")
        print("="*70)
        
        # Get deployment config from agent_config.json
        deployment_config = self.config.get_deployment_config()
        print(f"   Config: {deployment_config.get('initial_decoys', 3)} decoys, {deployment_config.get('initial_honeytokens', 5)} honeytokens")
        
        if self.setup.setup_all(deployment_config):
            print("\n✓ Honeytokens deployed successfully")
            
            # Register deployed decoys with backend
            deployed_decoys = self.setup.get_deployed_decoys()
            node_id = self.config.get_node_id()
            node_api_key = self.config.get_node_api_key()
            
            if node_id and node_api_key and deployed_decoys:
                self.registration.register_deployed_decoys(
                    node_id, 
                    node_api_key, 
                    deployed_decoys
                )
            
            return True
        else:
            print("\n✗ Failed to deploy honeytokens")
            return False
    
    def initialize_monitoring(self) -> bool:
        """Initialize file monitoring"""
        print("\n" + "="*70)
        print("👀 PHASE 2: MONITORING INITIALIZATION")
        print("="*70)
        
        if self.monitor.initialize_monitoring():
            print("\n✓ Monitoring initialized successfully")
            return True
        else:
            print("\n✗ Failed to initialize monitoring")
            return False
    
    def check_backend(self) -> bool:
        """Check backend API availability"""
        print("\n" + "="*70)
        print("📡 PHASE 3: BACKEND API CHECK")
        print("="*70)
        
        if self.sender.check_api_health():
            print("\n✓ Backend API is available")
            return True
        else:
            print("\n⚠️  Backend API is NOT available")
            print("   Start with: python ml_api.py")
            print("   (Agent will still monitor, but won't send alerts)")
            return False
    
    def run_once(self):
        """Run one monitoring cycle"""
        alerts = self.monitor.monitor_once()
        
        if alerts and self.sender.check_api_health():
            for alert in alerts:
                self.sender.send_alert(alert)
    
    def start(self, interval: int = 5, check_backend: bool = True):
        """
        Start the deception agent
        
        Args:
            interval: Monitoring interval in seconds
            check_backend: Whether to check backend before running
        """
        
        # Phase 0: Register with backend (if not already registered)
        if not ensure_agent_registered(self.config):
            print("\n✗ Agent startup failed - not registered")
            return False
        
        # Phase 1: Deploy honeytokens
        if not self.setup_honeytokens():
            print("\n✗ Agent startup failed")
            return False
        
        # Phase 2: Initialize monitoring
        if not self.initialize_monitoring():
            print("\n✗ Agent startup failed")
            return False
        
        # Phase 3: Check backend (optional)
        backend_available = self.check_backend() if check_backend else False
        
        # Phase 4: Start continuous monitoring
        print("\n" + "="*70)
        print("⚡ PHASE 4: CONTINUOUS MONITORING")
        print("="*70)
        print(f"\n🟢 AGENT ACTIVE")
        print(f"   Node ID: {self.config.get_node_id()}")
        print(f"   Honeytokens: {len(self.setup.honeytokens)} files deployed")
        print(f"   Monitoring: {self.watch_dir}")
        print(f"   Check interval: {interval} seconds")
        print(f"   Backend connection: {'✓ Active' if backend_available else '✗ Inactive'}")
        print(f"\n   Press Ctrl+C to stop\n")
        
        self.running = True
        
        try:
            while self.running:
                self.run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the agent gracefully"""
        self.running = False
        print("\n\n" + "="*70)
        print("🛑 AGENT STOPPED")
        print("="*70)
        self.print_summary()
    
    def print_summary(self):
        """Print agent summary"""
        print(f"\n📊 SUMMARY")
        print(f"   Honeytokens: {len(self.setup.honeytokens)} deployed")
        print(f"   Alerts detected: {len(self.monitor.alerts)}")
        print(f"   Alerts sent: {self.sender.alerts_sent}")
        print(f"   Alerts failed: {self.sender.alerts_failed}")
        
        if self.monitor.alerts:
            print(f"\n🚨 DETECTED ATTACKS:")
            for alert in self.monitor.alerts:
                print(f"   • {alert['file_accessed']} - {alert['action']} by {alert['username']}")


def demo_mode():
    """Run agent in demo mode (1 check cycle)"""
    print("\n" + "="*70)
    print("🎬 DEMO MODE - Single Monitoring Cycle")
    print("="*70)
    
    agent = DeceptionAgent()
    agent.setup_honeytokens()
    agent.initialize_monitoring()
    agent.check_backend()
    
    print("\n" + "="*70)
    print("👀 Checking for file access...")
    print("="*70)
    print("\n💡 TIP: Manually open a file from system_cache folder to trigger alert")
    print("   Example: Open system_cache/aws_keys.txt\n")
    
    # Run for 30 seconds in demo mode
    print("Monitoring for 30 seconds...\n")
    start_time = time.time()
    while time.time() - start_time < 30:
        agent.run_once()
        time.sleep(2)
    
    agent.print_summary()


def main():
    """Main entry point"""
    
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  🕷️  ENDPOINT DECEPTION AGENT - HONEYTOKEN DEPLOYMENT 🕷️  ".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    # Check arguments
    demo = '--demo' in sys.argv
    
    if demo:
        demo_mode()
    else:
        # Production mode
        agent = DeceptionAgent()
        agent.start(interval=5, check_backend=True)


if __name__ == '__main__':
    main()
