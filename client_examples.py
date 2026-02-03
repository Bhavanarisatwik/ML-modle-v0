"""
Python Client Examples for ML Classifier API
Demonstrates various ways to use the cyber attack classifier
"""

import requests
import json
from typing import Dict, List, Any
import time


class MLClassifierClient:
    """Client for interacting with ML Classifier API"""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """Initialize client with API URL"""
        self.api_url = api_url
        self.base_url = api_url.rstrip('/')
    
    def check_health(self) -> bool:
        """Check if API is healthy"""
        try:
            response = requests.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False
    
    def predict(self, log_data: Dict[str, int]) -> Dict[str, Any]:
        """
        Get prediction for a single log
        
        Args:
            log_data: Dictionary with security log features
        
        Returns:
            Prediction result
        """
        response = requests.post(
            f"{self.base_url}/predict",
            json=log_data
        )
        response.raise_for_status()
        return response.json()
    
    def predict_batch(self, logs: List[Dict[str, int]]) -> Dict[str, Any]:
        """
        Get predictions for multiple logs
        
        Args:
            logs: List of log dictionaries
        
        Returns:
            Batch prediction results
        """
        response = requests.post(
            f"{self.base_url}/predict-batch",
            json={"logs": logs}
        )
        response.raise_for_status()
        return response.json()
    
    def get_features(self) -> Dict[str, Any]:
        """Get feature information"""
        response = requests.get(f"{self.base_url}/features")
        response.raise_for_status()
        return response.json()


# =======================
# EXAMPLE 1: Simple Usage
# =======================
def example_simple_prediction():
    """Simple single prediction"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Simple Prediction")
    print("="*70)
    
    client = MLClassifierClient()
    
    # Check API is running
    if not client.check_health():
        print("✗ API is not running. Start it with: python ml_api.py")
        return
    
    # Create a log
    log = {
        "failed_logins": 120,
        "request_rate": 200,
        "commands_count": 0,
        "sql_payload": 0,
        "honeytoken_access": 0,
        "session_time": 600
    }
    
    print("\nInput Log:")
    print(json.dumps(log, indent=2))
    
    # Get prediction
    result = client.predict(log)
    
    print(f"\nPrediction Result:")
    print(f"  Attack Type: {result['attack_type']}")
    print(f"  Risk Score: {result['risk_score']}/10")
    print(f"  Confidence: {result['confidence']:.2%}")
    print(f"  Is Anomaly: {result['is_anomaly']}")
    
    # Interpret result
    if result['risk_score'] >= 7:
        print(f"\n⚠️  HIGH RISK - This appears to be a {result['attack_type']} attack!")
    else:
        print(f"\n✓ LOW RISK - Appears to be normal activity")


# =======================
# EXAMPLE 2: Batch Processing
# =======================
def example_batch_prediction():
    """Process multiple logs at once"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Batch Prediction (3 logs)")
    print("="*70)
    
    client = MLClassifierClient()
    
    # Multiple logs to process
    logs = [
        {  # Brute force attack
            "failed_logins": 100,
            "request_rate": 100,
            "commands_count": 0,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 500
        },
        {  # SQL injection
            "failed_logins": 1,
            "request_rate": 50,
            "commands_count": 1,
            "sql_payload": 1,
            "honeytoken_access": 0,
            "session_time": 120
        },
        {  # Normal traffic
            "failed_logins": 0,
            "request_rate": 30,
            "commands_count": 2,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 300
        }
    ]
    
    print(f"\nProcessing {len(logs)} logs...")
    
    # Get batch predictions
    result = client.predict_batch(logs)
    
    print(f"\nResults:")
    print(f"  Total Processed: {result['total_processed']}")
    print(f"  High Risk Count: {result['high_risk_count']}")
    
    print(f"\nDetailed Results:")
    for i, pred in enumerate(result['results'], 1):
        print(f"\n  [{i}] {pred['attack_type'].upper()}")
        print(f"      Risk Score: {pred['risk_score']}/10")
        print(f"      Confidence: {pred['confidence']:.2%}")


# =======================
# EXAMPLE 3: Real-time Monitoring
# =======================
def example_monitoring_simulation():
    """Simulate real-time log monitoring"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Real-time Log Monitoring (simulated)")
    print("="*70)
    
    client = MLClassifierClient()
    
    # Simulated logs coming from a system
    incoming_logs = [
        ("User Login", {
            "failed_logins": 0,
            "request_rate": 5,
            "commands_count": 0,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 60
        }),
        ("Database Query", {
            "failed_logins": 0,
            "request_rate": 10,
            "commands_count": 1,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 30
        }),
        ("Suspicious Activity", {
            "failed_logins": 50,
            "request_rate": 500,
            "commands_count": 15,
            "sql_payload": 1,
            "honeytoken_access": 1,
            "session_time": 120
        }),
    ]
    
    print("\nMonitoring incoming logs...\n")
    
    alerts = []
    
    for event_name, log in incoming_logs:
        print(f"[LOG] {event_name}...", end=" ", flush=True)
        
        result = client.predict(log)
        
        print(f"{result['attack_type']} (Risk: {result['risk_score']}/10)")
        
        # Generate alert if high risk
        if result['risk_score'] >= 7:
            alert = {
                "event": event_name,
                "attack_type": result['attack_type'],
                "risk_score": result['risk_score'],
                "confidence": result['confidence']
            }
            alerts.append(alert)
            print(f"     ⚠️  ALERT TRIGGERED!")
        
        time.sleep(0.5)  # Simulate processing delay
    
    # Summary
    print(f"\n{'='*70}")
    print(f"Monitoring Summary:")
    print(f"  Total Logs: {len(incoming_logs)}")
    print(f"  Alerts: {len(alerts)}")
    
    if alerts:
        print(f"\nAlert Details:")
        for i, alert in enumerate(alerts, 1):
            print(f"  [{i}] {alert['event']}")
            print(f"      Type: {alert['attack_type']}")
            print(f"      Risk: {alert['risk_score']}/10")


# =======================
# EXAMPLE 4: Custom Alert System
# =======================
def example_alert_system():
    """Implement a custom alert system"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Custom Alert System")
    print("="*70)
    
    client = MLClassifierClient()
    
    class AlertLevel:
        """Alert levels based on risk score"""
        LOW = (1, 3, "🟢 Low Risk - Normal activity")
        MEDIUM = (4, 6, "🟡 Medium Risk - Monitor")
        HIGH = (7, 8, "🔴 High Risk - Investigate")
        CRITICAL = (9, 10, "🔥 Critical Risk - IMMEDIATE ACTION")
    
    # Test logs with different risk profiles
    test_logs = [
        ("Routine Check", {
            "failed_logins": 1,
            "request_rate": 20,
            "commands_count": 2,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 200
        }),
        ("Unusual Activity", {
            "failed_logins": 45,
            "request_rate": 250,
            "commands_count": 10,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 400
        }),
        ("Attack Detected", {
            "failed_logins": 120,
            "request_rate": 500,
            "commands_count": 18,
            "sql_payload": 1,
            "honeytoken_access": 1,
            "session_time": 550
        }),
    ]
    
    print("\nProcessing with custom alert levels:\n")
    
    for event_name, log in test_logs:
        result = client.predict(log)
        risk = result['risk_score']
        
        # Determine alert level
        if AlertLevel.LOW[0] <= risk <= AlertLevel.LOW[1]:
            alert_msg = AlertLevel.LOW[2]
        elif AlertLevel.MEDIUM[0] <= risk <= AlertLevel.MEDIUM[1]:
            alert_msg = AlertLevel.MEDIUM[2]
        elif AlertLevel.HIGH[0] <= risk <= AlertLevel.HIGH[1]:
            alert_msg = AlertLevel.HIGH[2]
        else:
            alert_msg = AlertLevel.CRITICAL[2]
        
        print(f"{event_name}")
        print(f"  Attack: {result['attack_type']}")
        print(f"  Risk: {risk}/10")
        print(f"  {alert_msg}")
        print()


# =======================
# EXAMPLE 5: Feature Information
# =======================
def example_feature_info():
    """Display feature information"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Feature Information")
    print("="*70)
    
    client = MLClassifierClient()
    
    features = client.get_features()
    
    print("\nFeature Order:")
    for i, feature in enumerate(features['feature_order'], 1):
        print(f"  {i}. {feature}")
    
    print(f"\nFeature Ranges:")
    for feature, ranges in features['feature_ranges'].items():
        print(f"  {feature}: {ranges['min']}-{ranges['max']}")


# =======================
# EXAMPLE 6: Error Handling
# =======================
def example_error_handling():
    """Demonstrate proper error handling"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Error Handling")
    print("="*70)
    
    client = MLClassifierClient()
    
    # Test 1: API not available
    print("\n1. Checking API availability...")
    if client.check_health():
        print("   ✓ API is healthy")
    else:
        print("   ✗ API is not available - Make sure it's running!")
        return
    
    # Test 2: Invalid input (out of range)
    print("\n2. Testing invalid input (out of range)...")
    try:
        invalid_log = {
            "failed_logins": 999,  # Out of range (0-150)
            "request_rate": 50,
            "commands_count": 0,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 300
        }
        result = client.predict(invalid_log)
        print(f"   Response: {result['attack_type']}")
    except requests.exceptions.HTTPError as e:
        print(f"   ✓ Caught validation error: {e.response.status_code}")
    
    # Test 3: Missing field
    print("\n3. Testing missing required field...")
    try:
        incomplete_log = {
            "failed_logins": 50,
            "request_rate": 50,
            # Missing other fields
        }
        result = client.predict(incomplete_log)
    except requests.exceptions.HTTPError as e:
        print(f"   ✓ Caught error: {e.response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ✓ Caught error: {str(e)}")


# =======================
# EXAMPLE 7: Performance Testing
# =======================
def example_performance_testing():
    """Test API performance"""
    print("\n" + "="*70)
    print("EXAMPLE 7: Performance Testing")
    print("="*70)
    
    client = MLClassifierClient()
    
    # Create test logs
    test_log = {
        "failed_logins": 50,
        "request_rate": 100,
        "commands_count": 5,
        "sql_payload": 0,
        "honeytoken_access": 0,
        "session_time": 300
    }
    
    # Test single prediction latency
    print("\nTesting single prediction latency...")
    start = time.time()
    for i in range(10):
        result = client.predict(test_log)
    elapsed = time.time() - start
    
    print(f"  10 predictions took {elapsed:.3f} seconds")
    print(f"  Average: {(elapsed/10)*1000:.2f} ms per prediction")
    
    # Test batch prediction
    print("\nTesting batch prediction...")
    batch_logs = [test_log] * 100
    
    start = time.time()
    result = client.predict_batch(batch_logs)
    elapsed = time.time() - start
    
    print(f"  100 predictions took {elapsed:.3f} seconds")
    print(f"  Average: {(elapsed/100)*1000:.2f} ms per prediction")
    print(f"  Throughput: {100/elapsed:.0f} predictions/second")


# =======================
# MAIN RUNNER
# =======================
def run_all_examples():
    """Run all examples"""
    examples = [
        ("Simple Prediction", example_simple_prediction),
        ("Batch Prediction", example_batch_prediction),
        ("Monitoring Simulation", example_monitoring_simulation),
        ("Alert System", example_alert_system),
        ("Feature Information", example_feature_info),
        ("Error Handling", example_error_handling),
        ("Performance Testing", example_performance_testing),
    ]
    
    print("\n" + "="*70)
    print("ML CLASSIFIER API - CLIENT EXAMPLES")
    print("="*70)
    print("\nAvailable Examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    while True:
        choice = input("\nEnter example number (1-7) or 'all' for all, 'q' to quit: ").strip().lower()
        
        if choice == 'q':
            break
        elif choice == 'all':
            for name, func in examples:
                try:
                    func()
                except Exception as e:
                    print(f"✗ Error in {name}: {e}")
        elif choice.isdigit() and 1 <= int(choice) <= len(examples):
            try:
                examples[int(choice)-1][1]()
            except Exception as e:
                print(f"✗ Error: {e}")
        else:
            print("Invalid choice. Try again.")


if __name__ == '__main__':
    # Uncomment to run specific example:
    # example_simple_prediction()
    # example_batch_prediction()
    # example_monitoring_simulation()
    # example_alert_system()
    # example_feature_info()
    # example_error_handling()
    # example_performance_testing()
    
    # Or run interactive menu:
    run_all_examples()
