"""
FastAPI ML Microservice for Cyber Attack Detection
Provides REST API endpoint for attack prediction
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import json

from predict import AttackPredictor, NetworkPredictor
from feature_extractor import FeatureExtractor

# Initialize FastAPI app
app = FastAPI(
    title="Cyber Attack Behavior Classifier API",
    description="ML microservice for detecting and classifying cyber attacks",
    version="1.0.0"
)

# Initialize predictors (loaded once at startup)
try:
    predictor = AttackPredictor('.')
    network_predictor = NetworkPredictor('backend')
    print("✓ Models loaded successfully")
except Exception as e:
    print(f"✗ Error loading models: {e}")
    predictor = None
    network_predictor = None


# Request/Response Models
class SecurityLogInput(BaseModel):
    """Input model for security log prediction"""
    failed_logins: int = Field(..., ge=0, le=150, description="Number of failed login attempts (0-150)")
    request_rate: int = Field(..., ge=1, le=600, description="HTTP requests per second (1-600)")
    commands_count: int = Field(..., ge=0, le=20, description="Number of executed commands (0-20)")
    sql_payload: int = Field(..., ge=0, le=1, description="SQL injection detected (0 or 1)")
    honeytoken_access: int = Field(..., ge=0, le=1, description="Honeytoken accessed (0 or 1)")
    session_time: int = Field(..., ge=10, le=600, description="Session duration in seconds (10-600)")
    
    class Config:
        example = {
            "failed_logins": 85,
            "request_rate": 450,
            "commands_count": 8,
            "sql_payload": 1,
            "honeytoken_access": 0,
            "session_time": 300
        }


class PredictionResponse(BaseModel):
    """Output model for prediction response"""
    attack_type: str = Field(..., description="Predicted attack type")
    risk_score: int = Field(..., ge=1, le=10, description="Risk score from 1-10")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level of prediction")
    anomaly_score: float = Field(..., description="Raw anomaly detection score")
    is_anomaly: bool = Field(..., description="Whether flagged as anomalous")
    
    class Config:
        example = {
            "attack_type": "Injection",
            "risk_score": 9,
            "confidence": 0.95,
            "anomaly_score": -0.8234,
            "is_anomaly": True
        }


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Check API and model status"""
    return {
        "status": "healthy" if predictor else "unhealthy",
        "model_loaded": predictor is not None,
        "version": "1.0.0"
    }


# Main prediction endpoint
@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Prediction"],
    summary="Predict cyber attack type and risk score",
    responses={
        200: {"description": "Successful prediction"},
        400: {"description": "Invalid input"},
        500: {"description": "Model not loaded"}
    }
)
async def predict_attack(log_data: SecurityLogInput) -> PredictionResponse:
    """
    Predict attack type and compute risk score from security log data.
    
    **Features:**
    - **failed_logins**: Count of failed login attempts
    - **request_rate**: HTTP requests per second
    - **commands_count**: Number of commands executed
    - **sql_payload**: Whether SQL injection detected (0/1)
    - **honeytoken_access**: Whether honeytoken was accessed (0/1)
    - **session_time**: Duration of session in seconds
    
    **Returns:**
    - **attack_type**: Classification (Normal, BruteForce, Injection, DataExfil, Recon)
    - **risk_score**: Numeric risk level (1-10)
    - **confidence**: Prediction confidence (0-1)
    - **anomaly_score**: Anomaly detection score
    - **is_anomaly**: Boolean anomaly flag
    """
    
    if predictor is None:
        raise HTTPException(
            status_code=500,
            detail="ML models not loaded. Please check server logs."
        )
    
    try:
        # Convert input to dictionary
        log_dict = log_data.dict()
        
        # Get prediction
        prediction = predictor.predict(log_dict)
        
        # Return formatted response
        return PredictionResponse(
            attack_type=prediction['attack_type'],
            risk_score=prediction['risk_score'],
            confidence=prediction['confidence'],
            anomaly_score=prediction['anomaly_score'],
            is_anomaly=prediction['is_anomaly']
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction error: {str(e)}"
        )


# Batch prediction endpoint
class BatchPredictionRequest(BaseModel):
    """Batch prediction request"""
    logs: list[SecurityLogInput]


class BatchPredictionResponse(BaseModel):
    """Batch prediction response"""
    results: list[PredictionResponse]
    total_processed: int
    high_risk_count: int


@app.post(
    "/predict-batch",
    response_model=BatchPredictionResponse,
    tags=["Prediction"],
    summary="Predict for multiple security logs"
)
async def predict_batch(request: BatchPredictionRequest) -> BatchPredictionResponse:
    """
    Process multiple security logs in a single request.
    
    **Returns:**
    - List of predictions
    - Total logs processed
    - Count of high-risk (score >= 7) detections
    """
    
    if predictor is None:
        raise HTTPException(
            status_code=500,
            detail="ML models not loaded"
        )
    
    try:
        results = []
        high_risk_count = 0
        
        for log_data in request.logs:
            log_dict = log_data.dict()
            prediction = predictor.predict(log_dict)
            
            response = PredictionResponse(
                attack_type=prediction['attack_type'],
                risk_score=prediction['risk_score'],
                confidence=prediction['confidence'],
                anomaly_score=prediction['anomaly_score'],
                is_anomaly=prediction['is_anomaly']
            )
            
            results.append(response)
            
            if prediction['risk_score'] >= 7:
                high_risk_count += 1
        
        return BatchPredictionResponse(
            results=results,
            total_processed=len(results),
            high_risk_count=high_risk_count
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch prediction error: {str(e)}"
        )


# --- NETWORK PREDICTION ---

class NetworkFlowInput(BaseModel):
    """Input model for network flow prediction (derived from Zeek log)"""
    duration: float = Field(..., description="Flow duration")
    orig_pkts: int = Field(..., description="Total Fwd Packets")
    resp_pkts: int = Field(..., description="Total Bwd Packets")
    orig_bytes: float = Field(..., description="Total Length of Fwd Packets")
    resp_bytes: float = Field(..., description="Total Length of Bwd Packets")
    flow_bytes_s: float = Field(..., description="Flow Bytes/s")
    flow_pkts_s: float = Field(..., description="Flow Packets/s")
    dst_port: int = Field(..., description="Destination Port")
    protocol: int = Field(..., description="Protocol (e.g., 6 for TCP, 17 for UDP)")

class NetworkPredictionResponse(BaseModel):
    """Output model for network prediction response"""
    label: str = Field(..., description="Predicted network attack type")
    confidence: float = Field(..., description="Confidence of the prediction")

class NetworkBatchRequest(BaseModel):
    flows: list[NetworkFlowInput]

class NetworkBatchResponse(BaseModel):
    predictions: list[NetworkPredictionResponse]


@app.post(
    "/predict/network",
    response_model=NetworkBatchResponse,
    tags=["Prediction"],
    summary="Predict network attack types from flow data"
)
async def predict_network_batch(request: NetworkBatchRequest) -> NetworkBatchResponse:
    """
    Process multiple network flows in a single request (L3/L4 layer).
    """
    if network_predictor is None:
        raise HTTPException(status_code=500, detail="Network ML models not loaded")
        
    try:
        results = []
        for flow_data in request.flows:
            # Predict
            pred = network_predictor.predict(flow_data.dict())
            results.append(NetworkPredictionResponse(
                label=pred['label'],
                confidence=pred['confidence']
            ))
            
        return NetworkBatchResponse(predictions=results)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Network prediction error: {str(e)}"
        )



# Feature info endpoint
@app.get("/features", tags=["System"])
async def get_features():
    """Get information about input features"""
    return {
        "feature_order": FeatureExtractor.FEATURE_ORDER,
        "total_features": len(FeatureExtractor.FEATURE_ORDER),
        "feature_ranges": {
            "failed_logins": {"min": 0, "max": 150},
            "request_rate": {"min": 1, "max": 600},
            "commands_count": {"min": 0, "max": 20},
            "sql_payload": {"min": 0, "max": 1},
            "honeytoken_access": {"min": 0, "max": 1},
            "session_time": {"min": 10, "max": 600}
        }
    }


# API info endpoint
@app.get("/", tags=["System"])
async def root():
    """API information and available endpoints"""
    return {
        "name": "Cyber Attack Behavior Classifier API",
        "version": "1.0.0",
        "description": "ML microservice for cyber attack detection and classification",
        "endpoints": {
            "health": "/health",
            "single_prediction": "/predict",
            "batch_prediction": "/predict-batch",
            "network_prediction": "/predict/network",
            "features": "/features",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🚀 Starting Cyber Attack Classifier API...")
    print("="*60)
    print("\nAPI Documentation: http://localhost:8000/docs")
    print("Alternative Docs: http://localhost:8000/redoc")
    print("Health Check: http://localhost:8000/health")
    print("="*60 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
