"""
ML Service Integration
Sends data to ML API for prediction with timeout and fallback
"""

import requests
from typing import Dict, Any, Optional
import logging

from backend.models.log_models import MLPrediction
from backend.config import ML_PREDICT_ENDPOINT

logger = logging.getLogger(__name__)


class MLService:
    """ML model prediction service with fallback handling"""
    
    def __init__(self):
        self.predict_url = ML_PREDICT_ENDPOINT
    
    async def predict_attack(self, log_data: Dict[str, Any]) -> Optional[MLPrediction]:
        """
        Send log data to ML API for attack prediction
        
        Args:
            log_data: Dictionary with ML input features
        
        Returns:
            MLPrediction (never None - uses fallback if ML fails)
        """
        try:
            # Convert log data to ML features
            ml_input = self._convert_to_ml_features(log_data)
            
            # Call ML API with timeout and error handling
            response = requests.post(
                self.predict_url,
                json=ml_input,
                timeout=3  # 3-second timeout to prevent hanging
            )
            
            if response.status_code == 200:
                result = response.json()
                return MLPrediction(
                    attack_type=result["attack_type"],
                    risk_score=result["risk_score"],
                    confidence=result["confidence"],
                    is_anomaly=result["is_anomaly"]
                )
            else:
                logger.error(f"ML API returned status {response.status_code}")
                return self._get_fallback_prediction()
                
        except requests.exceptions.Timeout:
            logger.error(f"ML API timeout (>{3}s) - using fallback prediction")
            return self._get_fallback_prediction()
        except requests.exceptions.ConnectionError:
            logger.error(f"ML API connection failed - using fallback prediction")
            return self._get_fallback_prediction()
        except requests.exceptions.RequestException as e:
            logger.error(f"ML API request error: {e} - using fallback prediction")
            return self._get_fallback_prediction()
        except Exception as e:
            logger.error(f"ML prediction error: {e} - using fallback prediction")
            return self._get_fallback_prediction()
    
    def _get_fallback_prediction(self) -> MLPrediction:
        """
        Return fallback prediction when ML service is unavailable
        
        Stores event with minimal risk scoring so it's not lost
        """
        logger.warning("⚠️ Using fallback prediction (ML service unavailable)")
        return MLPrediction(
            attack_type="unknown",
            risk_score=0,
            confidence=0.0,
            is_anomaly=False
        )
    
    @staticmethod
    def _convert_to_ml_features(log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert log data to ML features"""
        # Extract features for ML model
        return {
            "service": log_data.get("service", "unknown"),
            "source_ip": log_data.get("source_ip", "0.0.0.0"),
            "activity": log_data.get("activity", "unknown"),
            "payload": log_data.get("payload", ""),
            "hostname": log_data.get("hostname", "unknown"),
            "username": log_data.get("username", "unknown"),
            "file_accessed": log_data.get("file_accessed", "unknown")
        }


# Singleton instance
ml_service = MLService()
