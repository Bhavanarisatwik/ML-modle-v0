"""
Feature Extractor for Cyber Attack Logs
Extracts numeric features from security log JSON data
"""

from typing import Dict, List, Any
import json


class FeatureExtractor:
    """Extract features from security logs in consistent order"""
    
    # Feature columns in exact order as training data
    FEATURE_ORDER = [
        'failed_logins',
        'request_rate',
        'commands_count',
        'sql_payload',
        'honeytoken_access',
        'session_time'
    ]
    
    @staticmethod
    def extract_features(log_data: Dict[str, Any]) -> List[float]:
        """
        Extract numeric features from log JSON in correct order
        
        Args:
            log_data: Dictionary containing security log information
                - failed_logins (int): Number of failed login attempts
                - request_rate (int): HTTP requests per second
                - commands_count (int): Number of executed commands
                - sql_payload (int): 1 if SQL injection detected, 0 otherwise
                - honeytoken_access (int): 1 if honeytoken accessed, 0 otherwise
                - session_time (int): Session duration in seconds
        
        Returns:
            List of floats in correct feature order for model prediction
        """
        features = []
        
        for feature_name in FeatureExtractor.FEATURE_ORDER:
            # Get feature with default value 0 if missing
            value = log_data.get(feature_name, 0)
            
            # Validate and convert to float
            try:
                features.append(float(value))
            except (ValueError, TypeError):
                print(f"Warning: Invalid value for {feature_name}: {value}. Using 0.")
                features.append(0.0)
        
        return features
    
    @staticmethod
    def validate_features(log_data: Dict[str, Any]) -> bool:
        """
        Validate that log data contains all required features
        
        Args:
            log_data: Dictionary to validate
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = set(FeatureExtractor.FEATURE_ORDER)
        provided_fields = set(log_data.keys())
        
        if not required_fields.issubset(provided_fields):
            missing = required_fields - provided_fields
            print(f"Missing fields: {missing}")
            return False
        
        return True
    
    @staticmethod
    def extract_from_json_string(json_str: str) -> List[float]:
        """
        Extract features from JSON string
        
        Args:
            json_str: JSON string containing log data
        
        Returns:
            List of feature values
        """
        try:
            log_data = json.loads(json_str)
            return FeatureExtractor.extract_features(log_data)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return None


# Example usage
if __name__ == '__main__':
    # Example log data
    example_log = {
        'failed_logins': 120,
        'request_rate': 450,
        'commands_count': 5,
        'sql_payload': 1,
        'honeytoken_access': 0,
        'session_time': 300
    }
    
    print("Example log data:")
    print(json.dumps(example_log, indent=2))
    
    features = FeatureExtractor.extract_features(example_log)
    print(f"\nExtracted features: {features}")
    print(f"Feature order: {FeatureExtractor.FEATURE_ORDER}")
