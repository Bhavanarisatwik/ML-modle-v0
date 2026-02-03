"""
Test Cases for ML Cyber Attack Classifier
Contains example logs and test scenarios for different attack types
"""

import json
import requests
from typing import Dict, Any, List


class TestCases:
    """Collection of test cases for different attack scenarios"""
    
    # Test 1: SQL Injection Attack
    SQL_INJECTION = {
        "name": "SQL Injection Attack",
        "log": {
            "failed_logins": 2,
            "request_rate": 50,
            "commands_count": 1,
            "sql_payload": 1,
            "honeytoken_access": 0,
            "session_time": 120
        },
        "expected_attack": "Injection",
        "description": "Detected SQL payload in request"
    }
    
    # Test 2: Brute Force Attack
    BRUTE_FORCE = {
        "name": "Brute Force Attack",
        "log": {
            "failed_logins": 120,
            "request_rate": 200,
            "commands_count": 0,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 600
        },
        "expected_attack": "BruteForce",
        "description": "Multiple failed login attempts (>80)"
    }
    
    # Test 3: Reconnaissance Scan
    RECON_SCAN = {
        "name": "Reconnaissance Scan",
        "log": {
            "failed_logins": 5,
            "request_rate": 550,
            "commands_count": 2,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 180
        },
        "expected_attack": "Recon",
        "description": "High request rate indicating scanning activity (>400)"
    }
    
    # Test 4: Honeytoken Access (Data Exfiltration)
    HONEYTOKEN_ACCESS = {
        "name": "Honeytoken Access - Data Exfil",
        "log": {
            "failed_logins": 0,
            "request_rate": 100,
            "commands_count": 15,
            "sql_payload": 0,
            "honeytoken_access": 1,
            "session_time": 450
        },
        "expected_attack": "DataExfil",
        "description": "Unauthorized access to honey token"
    }
    
    # Test 5: Normal Behavior
    NORMAL_TRAFFIC = {
        "name": "Normal User Traffic",
        "log": {
            "failed_logins": 1,
            "request_rate": 50,
            "commands_count": 3,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 300
        },
        "expected_attack": "Normal",
        "description": "Legitimate user activity"
    }
    
    # Test 6: Complex Attack (Multiple Indicators)
    COMPLEX_ATTACK = {
        "name": "Complex Attack - Multiple Vectors",
        "log": {
            "failed_logins": 95,
            "request_rate": 450,
            "commands_count": 18,
            "sql_payload": 1,
            "honeytoken_access": 1,
            "session_time": 580
        },
        "expected_attack": "Injection",  # SQL payload takes precedence
        "description": "Multiple attack vectors detected simultaneously"
    }
    
    # Test 7: Edge Case - Minimum Values
    MINIMUM_VALUES = {
        "name": "Edge Case - Minimum Values",
        "log": {
            "failed_logins": 0,
            "request_rate": 1,
            "commands_count": 0,
            "sql_payload": 0,
            "honeytoken_access": 0,
            "session_time": 10
        },
        "expected_attack": "Normal",
        "description": "Minimal resource usage"
    }
    
    # Test 8: Edge Case - Maximum Values
    MAXIMUM_VALUES = {
        "name": "Edge Case - Maximum Values",
        "log": {
            "failed_logins": 150,
            "request_rate": 600,
            "commands_count": 20,
            "sql_payload": 1,
            "honeytoken_access": 1,
            "session_time": 600
        },
        "expected_attack": "Injection",
        "description": "Maximum values - severe attack scenario"
    }
    
    @classmethod
    def get_all_tests(cls) -> List[Dict[str, Any]]:
        """Get all test cases"""
        return [
            cls.SQL_INJECTION,
            cls.BRUTE_FORCE,
            cls.RECON_SCAN,
            cls.HONEYTOKEN_ACCESS,
            cls.NORMAL_TRAFFIC,
            cls.COMPLEX_ATTACK,
            cls.MINIMUM_VALUES,
            cls.MAXIMUM_VALUES
        ]
    
    @classmethod
    def print_test_case(cls, test_case: Dict[str, Any]):
        """Print a test case in readable format"""
        print(f"\n{'='*70}")
        print(f"📋 TEST: {test_case['name']}")
        print(f"{'='*70}")
        print(f"Description: {test_case['description']}")
        print(f"\nInput Log:")
        print(json.dumps(test_case['log'], indent=2))
        print(f"\nExpected Attack Type: {test_case['expected_attack']}")


class LocalTestRunner:
    """Run tests using local imports (no HTTP)"""
    
    def __init__(self):
        """Initialize with local predictor"""
        from predict import AttackPredictor
        self.predictor = AttackPredictor('.')
    
    def run_tests(self):
        """Run all test cases locally"""
        test_cases = TestCases.get_all_tests()
        
        print("\n" + "="*70)
        print("🧪 RUNNING LOCAL PREDICTION TESTS")
        print("="*70)
        
        passed = 0
        failed = 0
        
        for test in test_cases:
            TestCases.print_test_case(test)
            
            try:
                result = self.predictor.predict(test['log'])
                
                print(f"\nPrediction Result:")
                print(f"  Attack Type: {result['attack_type']}")
                print(f"  Risk Score: {result['risk_score']}/10")
                print(f"  Confidence: {result['confidence']:.2%}")
                print(f"  Anomaly Score: {result['anomaly_score']:.4f}")
                print(f"  Is Anomaly: {result['is_anomaly']}")
                
                # Check if prediction matches expected
                if result['attack_type'] == test['expected_attack']:
                    print(f"\n✓ PASS - Correctly predicted {test['expected_attack']}")
                    passed += 1
                else:
                    print(f"\n✗ FAIL - Expected {test['expected_attack']}, got {result['attack_type']}")
                    failed += 1
            
            except Exception as e:
                print(f"\n✗ ERROR: {str(e)}")
                failed += 1
        
        # Summary
        print(f"\n{'='*70}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Total Tests: {len(test_cases)}")
        print(f"✓ Passed: {passed}")
        print(f"✗ Failed: {failed}")
        print(f"Success Rate: {(passed/len(test_cases)*100):.1f}%")
        print(f"{'='*70}\n")


class APITestRunner:
    """Run tests using HTTP API"""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        """Initialize with API URL"""
        self.api_url = api_url
    
    def test_health(self):
        """Test health endpoint"""
        try:
            response = requests.get(f"{self.api_url}/health")
            print(f"✓ Health Check: {response.json()['status']}")
            return response.status_code == 200
        except Exception as e:
            print(f"✗ Health Check Failed: {e}")
            return False
    
    def run_single_test(self, test_case: Dict[str, Any]):
        """Run a single test via API"""
        TestCases.print_test_case(test_case)
        
        try:
            response = requests.post(
                f"{self.api_url}/predict",
                json=test_case['log']
            )
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"\nAPI Response:")
                print(f"  Attack Type: {result['attack_type']}")
                print(f"  Risk Score: {result['risk_score']}/10")
                print(f"  Confidence: {result['confidence']:.2%}")
                
                if result['attack_type'] == test_case['expected_attack']:
                    print(f"✓ PASS")
                    return True
                else:
                    print(f"✗ FAIL - Expected {test_case['expected_attack']}")
                    return False
            else:
                print(f"✗ API Error: {response.status_code}")
                print(response.text)
                return False
        
        except Exception as e:
            print(f"✗ Request Failed: {e}")
            return False
    
    def run_batch_test(self):
        """Test batch prediction endpoint"""
        test_cases = TestCases.get_all_tests()
        logs = [test['log'] for test in test_cases]
        
        print("\n" + "="*70)
        print("🧪 BATCH PREDICTION TEST")
        print("="*70)
        
        try:
            response = requests.post(
                f"{self.api_url}/predict-batch",
                json={"logs": logs}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✓ Batch Test Successful")
                print(f"  Total Processed: {result['total_processed']}")
                print(f"  High Risk Count: {result['high_risk_count']}")
                
                for i, pred in enumerate(result['results']):
                    print(f"\n  [{i+1}] {pred['attack_type']} (Risk: {pred['risk_score']}/10)")
                
                return True
            else:
                print(f"✗ Batch Test Failed: {response.status_code}")
                return False
        
        except Exception as e:
            print(f"✗ Batch Request Failed: {e}")
            return False
    
    def run_all_api_tests(self):
        """Run all API tests"""
        print("\n" + "="*70)
        print("🧪 RUNNING API TESTS")
        print("="*70)
        
        if not self.test_health():
            print("\n✗ API is not responding. Make sure it's running on port 8000")
            return
        
        test_cases = TestCases.get_all_tests()
        passed = 0
        
        for test in test_cases:
            if self.run_single_test(test):
                passed += 1
        
        self.run_batch_test()
        
        print(f"\n{'='*70}")
        print(f"📊 API TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Passed: {passed}/{len(test_cases)}")
        print(f"Success Rate: {(passed/len(test_cases)*100):.1f}%")
        print(f"{'='*70}\n")


def main():
    """Main test runner"""
    import sys
    
    # Determine which tests to run
    if len(sys.argv) > 1 and sys.argv[1] == 'api':
        # Run API tests
        runner = APITestRunner()
        runner.run_all_api_tests()
    else:
        # Run local tests (default)
        runner = LocalTestRunner()
        runner.run_tests()


if __name__ == '__main__':
    main()
