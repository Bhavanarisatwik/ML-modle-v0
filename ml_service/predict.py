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
        
        # Convert anomaly score to risk score (0-10)
        # Pass features for enhanced risk calculation
        risk_score = self._compute_risk_score(anomaly_score, confidence, attack_type, features)
        
        return {
            'attack_type': attack_type,
            'risk_score': risk_score,
            'confidence': float(confidence),
            'anomaly_score': float(anomaly_score),
            'is_anomaly': bool(is_anomaly),
            'features_used': self.feature_columns
        }
    
    def _compute_risk_score(self, anomaly_score: float, confidence: float, 
                           attack_type: str, features: list = None) -> int:
        """
        Compute risk score from 0-10 based on anomaly, confidence, and features
        
        Improved scoring for Decoyvers environment:
        - Confidence contributes 60% (0-6 points)
        - Anomaly score contributes 40% (0-4 points)
        - Honeytoken access adds +2 points
        - High failed logins adds +1 point
        
        Args:
            anomaly_score: Score from anomaly detector (negative values)
            confidence: Prediction confidence (0-1)
            attack_type: Predicted attack type
            features: Raw feature values (optional)
        
        Returns:
            Risk score from 0-10
        """
        # Base score from confidence (0-6 points)
        confidence_component = confidence * 6
        
        # Anomaly component (0-4 points)
        # Anomaly scores are negative, more negative = more anomalous
        # Normalize to 0-1 range, then scale to 0-4
        anomaly_normalized = min(max(abs(anomaly_score), 0), 1)
        anomaly_component = anomaly_normalized * 4
        
        # Combine base score
        risk_score = confidence_component + anomaly_component
        
        # Feature-based bonuses
        if features:
            failed_logins = features[0] if len(features) > 0 else 0
            honeytoken_access = features[4] if len(features) > 4 else 0
            
            # Honeytoken access is critical (+2 points)
            if honeytoken_access == 1:
                risk_score += 2
            
            # High failed logins indicate brute force (+1 point)
            if failed_logins > 50:
                risk_score += 1
        
        # Attack type boosts
        attack_boosts = {
            'DataExfil': 2.0,      # Honeytoken access = critical
            'Injection': 1.5,      # SQL injection very dangerous
            'BruteForce': 1.2,     # Brute force serious
            'Recon': 0.8,          # Reconnaissance lower priority
            'Normal': 0.3          # Normal traffic minimal risk
        }
        
        risk_score *= attack_boosts.get(attack_type, 1.0)
        
        # Clamp to 0-10 range
        risk_score = max(0, min(10, int(round(risk_score))))
        
        return risk_score


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
