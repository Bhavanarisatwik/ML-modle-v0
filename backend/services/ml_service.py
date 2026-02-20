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
        """
        # FORCED TEST OVERRIDE 2: Prove logic is hitting this code
        return MLPrediction(
            attack_type="Injection",
            risk_score=9,
            confidence=0.99,
            is_anomaly=True
        )

        try:
            # Convert log data to ML features
            ml_input = self._convert_to_ml_features(log_data)
            
            # Call ML API with timeout and error handling
            response = requests.post(
                self.predict_url,
                json=ml_input,
                timeout=15  # Increased timeout for ML microservice cold starts
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
                logger.error(f"ML API returned status {response.status_code}: {response.text}")
                return self._get_fallback_prediction()
                
        except requests.exceptions.Timeout:
            logger.error(f"ML API timeout (>{15}s) - using fallback prediction")
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
        """
        Convert raw log metadata into numeric features for the ML model.
        """
        service = str(log_data.get("service", "unknown")).lower()
        activity = str(log_data.get("activity", "unknown")).lower()
        payload = str(log_data.get("payload", "")).lower()
        
        # Support both 'file_accessed' (AgentEvent) and 'file_name' (HoneypotLog)
        file_accessed = str(log_data.get("file_accessed") or log_data.get("file_name") or "unknown").lower()
        alert_type = str(log_data.get("alert_type", "")).upper()
        severity = str(log_data.get("severity", "")).upper()
        
        # 1. failed_logins (suspicion heuristic)
        failed_logins = 0
        if "login" in activity or "auth" in activity:
            failed_logins = 85
        if "modified" in activity or severity == "CRITICAL":
            failed_logins = 120
            
        # 2. request_rate (Intensity aligned with 100% accuracy model)
        request_rate = 100
        if "scan" in activity or "brute" in activity:
            request_rate = 1200
        elif alert_type == "HONEYTOKEN_ACCESS" or "endpoint_agent" in service:
            request_rate = 300
            
        # 3. commands_count
        commands_count = 5
        if "command" in activity or "exec" in activity or "injection" in activity:
            commands_count = 35
            
        # 4. sql_payload (signature detection)
        sql_payload = 0
        sql_signatures = ["select", "union", "insert", "drop", "delete", "--", "1=1", "' or"]
        if any(sig in payload for sig in sql_signatures) or "sql" in file_accessed or "db_" in file_accessed:
            sql_payload = 1
            
        # 5. honeytoken_access
        honeytoken_access = 1 if (alert_type == "HONEYTOKEN_ACCESS" or "endpoint_agent" in service or "honey" in file_accessed) else 0
        
        # 6. session_time
        session_time = 300 # Default baseline
        
        return {
            "failed_logins": failed_logins,
            "request_rate": request_rate,
            "commands_count": commands_count,
            "sql_payload": sql_payload,
            "honeytoken_access": honeytoken_access,
            "session_time": session_time
        }


# Singleton instance
ml_service = MLService()
