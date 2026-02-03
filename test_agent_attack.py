#!/usr/bin/env python3
"""
Test script to trigger honeytoken alert during agent monitoring.
This simulates an attacker accessing fake credentials.
"""

import time
import subprocess
import threading
from pathlib import Path

def open_honeytoken_file():
    """Open a honeytoken file after 10 seconds to trigger alert"""
    time.sleep(10)  # Let agent start monitoring
    
    honeytoken_path = Path("system_cache") / "aws_keys.txt"
    if honeytoken_path.exists():
        print(f"\n🚨 TEST: Opening honeytoken file: {honeytoken_path}")
        # Open file to trigger access detection
        try:
            with open(honeytoken_path, 'r') as f:
                content = f.read()
            print("✓ File accessed successfully - Alert should be triggered!")
        except Exception as e:
            print(f"❌ Error accessing file: {e}")
    else:
        print(f"❌ Honeytoken file not found: {honeytoken_path}")

if __name__ == "__main__":
    print("=" * 70)
    print("🧪 HONEYTOKEN ATTACK SIMULATION TEST")
    print("=" * 70)
    print("\nThis test will:")
    print("1. Start agent in background monitoring")
    print("2. Wait 10 seconds for setup")
    print("3. Open a honeytoken file (simulating attack)")
    print("4. Watch real-time alert detection")
    print("\nStarting in 3 seconds...\n")
    
    time.sleep(3)
    
    # Start agent in separate thread
    print("Starting agent with 45-second monitoring window...\n")
    
    # Modify agent to run for 45 seconds instead of 30
    # We'll use subprocess to control timing
    
    def run_agent():
        """Run agent with extended demo mode"""
        import sys
        sys.path.insert(0, '.')
        from agent import DeceptionAgent
        
        agent = DeceptionAgent()
        # Setup
        agent.setup_honeytokens()
        agent.initialize_monitoring()
        agent.check_backend()
        
        # Run monitoring for 45 seconds
        print("\n" + "=" * 70)
        print("⚡ MONITORING ACTIVE - File access will trigger alert")
        print("=" * 70)
        
        # Monitor for 45 seconds with early trigger
        start_time = time.time()
        alert_count = 0
        
        while time.time() - start_time < 45:
            alerts = agent.monitor.monitor_once(callback=None)
            if alerts:
                print(f"\n🚨 ALERT DETECTED ({len(alerts)} alerts)")
                for alert in alerts:
                    print(f"   File: {alert['file_accessed']}")
                    print(f"   Action: {alert['action']}")
                    print(f"   Severity: {alert['severity']}")
                    
                    # Send to API
                    success = agent.sender.send_alert(alert)
                    if success:
                        pred = alert.get('ml_prediction', {})
                        print(f"   ✓ Sent to ML API")
                        print(f"     Attack Type: {pred.get('attack_type')}")
                        print(f"     Risk Score: {pred.get('risk_score')}/10")
                        print(f"     Confidence: {pred.get('confidence'):.1%}")
                    alert_count += 1
            
            time.sleep(5)
        
        print(f"\n{'=' * 70}")
        print(f"📊 Test Complete")
        print(f"   Alerts triggered: {alert_count}")
        print(f"   Expected: 1+ (depending on file access)")
        print(f"{'=' * 70}")
    
    # Start file opener in background
    opener_thread = threading.Thread(target=open_honeytoken_file, daemon=True)
    opener_thread.start()
    
    # Run agent
    run_agent()
