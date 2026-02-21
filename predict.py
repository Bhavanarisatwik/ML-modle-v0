"""
Prediction Script for Cyber Attack Behavior Classification
Uses trained models to predict attack type and compute risk score
"""

import joblib
import numpy as np
from typing import Dict, Tuple, Any
from feature_extractor import FeatureExtractor
import os


class AttackPredictor:
    def __init__(self, model_dir: str = '.'):
        """Load trained models from disk"""
        print("Loading trained models...")
        
        # Load models
        self.classifier = joblib.load(os.path.join(model_dir, 'classifier.pkl'))
        self.anomaly_model = joblib.load(os.path.join(model_dir, 'anomaly_model.pkl'))
        self.scaler = joblib.load(os.path.join(model_dir, 'scaler.pkl'))
        self.label_encoder = joblib.load(os.path.join(model_dir, 'label_encoder.pkl'))
        self.feature_columns = joblib.load(os.path.join(model_dir, 'feature_columns.pkl'))
        
        print("✓ All models loaded successfully")
    
    def predict(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict attack type and compute risk score
        
        Args:
            log_data: Dictionary containing security log features
        
        Returns:
            Dictionary with:
                - attack_type: Predicted attack classification
                - risk_score: Numeric risk from 1-10
                - confidence: Confidence level of prediction
                - anomaly_score: Raw anomaly score
                - is_anomaly: Whether flagged as anomaly
        """
        # Extract features in correct order
        features = FeatureExtractor.extract_features(log_data)
        features_array = np.array(features).reshape(1, -1)
        
        # Predict attack type
        attack_encoded = self.classifier.predict(features_array)[0]
        attack_type = self.label_encoder.inverse_transform([attack_encoded])[0]
        
        # Get prediction confidence
        probabilities = self.classifier.predict_proba(features_array)[0]
        confidence = float(np.max(probabilities))
        
        # Compute anomaly score
        features_scaled = self.scaler.transform(features_array)
        anomaly_score = self.anomaly_model.score_samples(features_scaled)[0]
        is_anomaly = self.anomaly_model.predict(features_scaled)[0] == -1
        
        # Convert anomaly score to risk score (1-10)
        # Anomaly scores are negative, more negative = more anomalous
        # Range typically -1 to ~0, we'll normalize to 1-10 scale
        risk_score = self._compute_risk_score(anomaly_score, confidence, attack_type)
        
        return {
            'attack_type': attack_type,
            'risk_score': risk_score,
            'confidence': float(confidence),
            'anomaly_score': float(anomaly_score),
            'is_anomaly': bool(is_anomaly),
            'features_used': self.feature_columns
        }
    
    def _compute_risk_score(self, anomaly_score: float, confidence: float, 
                           attack_type: str) -> int:
        """
        Compute risk score from 1-10 based on anomaly and confidence
        
        Args:
            anomaly_score: Score from anomaly detector (negative values)
            confidence: Prediction confidence (0-1)
            attack_type: Predicted attack type
        
        Returns:
            Risk score from 1-10
        """
        # Normalize anomaly score (-1 to 0 becomes 0 to 1)
        anomaly_normalized = min(max(abs(anomaly_score), 0), 1)
        
        # Base risk from anomaly detection (0-5)
        anomaly_risk = anomaly_normalized * 5
        
        # Add confidence-based risk (0-5)
        # Higher confidence in non-normal attacks = higher risk
        confidence_risk = confidence * 5 if attack_type != 'Normal' else confidence * 2
        
        # Combine scores
        raw_risk = anomaly_risk * 0.4 + confidence_risk * 0.6
        
        # Attack type multiplier
        attack_multipliers = {
            'Injection': 1.3,      # SQL injection is very dangerous
            'BruteForce': 1.1,     # Brute force is serious
            'DataExfil': 1.2,      # Data theft is serious
            'Recon': 0.9,          # Reconnaissance is less immediate threat
            'Normal': 0.3           # Normal traffic has low risk
        }
        
        final_risk = raw_risk * attack_multipliers.get(attack_type, 1.0)
        
        # Ensure score is between 1-10
        risk_score = max(1, min(10, int(final_risk)))
        
        return risk_score

class NetworkPredictor:
    def __init__(self, model_dir: str = 'backend'):
        """Load trained network models from disk"""
        print("Loading trained network models...")
        
        # Load network models
        self.classifier = joblib.load(os.path.join(model_dir, 'network_classifier.pkl'))
        self.scaler = joblib.load(os.path.join(model_dir, 'network_scaler.pkl'))
        self.label_encoder = joblib.load(os.path.join(model_dir, 'network_label_encoder.pkl'))
        self.feature_columns = joblib.load(os.path.join(model_dir, 'network_feature_columns.pkl'))
        
        print("✓ All network models loaded successfully")

    def predict(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict network attack type
        """
        # Build features array in exact order of feature_columns
        features = []
        for col in self.feature_columns:
            features.append(float(flow_data.get(col, 0.0)))
            
        features_array = np.array(features).reshape(1, -1)
        
        # Scale features
        features_scaled = self.scaler.transform(features_array)
        
        # Predict
        attack_encoded = self.classifier.predict(features_scaled)[0]
        attack_type = self.label_encoder.inverse_transform([attack_encoded])[0]
        
        # Confidence
        probabilities = self.classifier.predict_proba(features_scaled)[0]
        confidence = float(np.max(probabilities))
        
        return {
            'label': attack_type,
            'confidence': confidence,
            'features_used': self.feature_columns
        }

def predict_batch(log_list: list, model_dir: str = '.') -> list:
    """
    Predict for multiple logs
    
    Args:
        log_list: List of log dictionaries
        model_dir: Directory containing model files
    
    Returns:
        List of prediction results
    """
    predictor = AttackPredictor(model_dir)
    results = []
    
    for log in log_list:
        result = predictor.predict(log)
        results.append(result)
    
    return results


def main():
    """Example usage"""
    # Test logs
    test_logs = [
        {
            'failed_logins': 120,
            'request_rate': 50,
            'commands_count': 3,
            'sql_payload': 1,
            'honeytoken_access': 0,
            'session_time': 300
        },
        {
            'failed_logins': 10,
            'request_rate': 450,
            'commands_count': 2,
            'sql_payload': 0,
            'honeytoken_access': 0,
            'session_time': 200
        }
    ]
    
    predictor = AttackPredictor('.')
    
    for i, log in enumerate(test_logs, 1):
        print(f"\n{'='*50}")
        print(f"Test Log {i}: {log}")
        result = predictor.predict(log)
        print(f"\nPrediction:")
        print(f"  Attack Type: {result['attack_type']}")
        print(f"  Risk Score: {result['risk_score']}/10")
        print(f"  Confidence: {result['confidence']:.2%}")
        print(f"  Anomaly Score: {result['anomaly_score']:.4f}")
        print(f"  Is Anomaly: {result['is_anomaly']}")


if __name__ == '__main__':
    main()
