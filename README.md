# 🧠 ML-Based Cyber Attack Behavior Classifier

A complete machine learning microservice for detecting and classifying cyber attacks using behavioral analysis.

## 📋 Project Overview

This system detects and classifies cyber attacks into 5 categories:
- **Normal** - Legitimate user activity
- **BruteForce** - Multiple failed login attempts
- **Injection** - SQL injection attacks
- **DataExfil** - Data exfiltration attempts
- **Recon** - Reconnaissance/scanning activities

## 🏗️ Architecture

```
┌─────────────────┐
│  Security Logs  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│      Feature Extraction Module          │
│  (feature_extractor.py)                 │
│  - Normalize log data                   │
│  - Extract numeric features             │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│       ML Prediction Engine              │
│  (predict.py)                           │
│  - RandomForest Classifier              │
│  - IsolationForest Anomaly Detector     │
│  - Risk Score Computation               │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│      REST API Service (FastAPI)         │
│  (ml_api.py)                            │
│  - /predict endpoint                    │
│  - /predict-batch endpoint              │
│  - /health endpoint                     │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   Client Apps   │
│  (curl, Python, │
│   Postman, etc) │
└─────────────────┘
```

## 📂 File Structure

```
ML-modle v0/
├── requirements.txt           # Python dependencies
├── dataset_generator.py       # Synthetic data generation
├── train_model.py            # Model training pipeline
├── feature_extractor.py      # Feature extraction logic
├── predict.py                # Prediction engine
├── ml_api.py                 # FastAPI service
├── test_cases.py             # Test suite
├── training_data.csv         # Generated dataset (after step 1)
├── classifier.pkl            # Trained RandomForest (after step 2)
├── anomaly_model.pkl         # Trained IsolationForest (after step 2)
├── scaler.pkl                # Feature scaler (after step 2)
├── label_encoder.pkl         # Label encoder (after step 2)
├── feature_columns.pkl       # Feature names (after step 2)
├── README.md                 # This file
└── COMPLETE_GUIDE.md         # Detailed setup guide
```

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Generate Training Data

```bash
python dataset_generator.py
```

**Output:**
- `training_data.csv` - 1000 rows of synthetic attack data
- Shows label distribution and preview

### Step 3: Train ML Models

```bash
python train_model.py
```

**Output:**
- `classifier.pkl` - RandomForest classifier (Random attacks)
- `anomaly_model.pkl` - IsolationForest (Anomaly detection)
- `scaler.pkl` - StandardScaler (Feature normalization)
- `label_encoder.pkl` - Label encoding mapping
- `feature_columns.pkl` - Feature column names

### Step 4: Run Local Tests

```bash
python test_cases.py
```

Tests 8 different attack scenarios locally.

### Step 5: Start API Server

```bash
python ml_api.py
```

API will start on `http://localhost:8000`

### Step 6: Test API Endpoints

In a new terminal:

```bash
python test_cases.py api
```

Or use curl/Postman with examples below.

## 🔧 Input Features

The model expects 6 numeric features:

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `failed_logins` | int | 0-150 | Failed login attempts |
| `request_rate` | int | 1-600 | HTTP requests/second |
| `commands_count` | int | 0-20 | Executed commands |
| `sql_payload` | int | 0-1 | SQL injection detected (1) or not (0) |
| `honeytoken_access` | int | 0-1 | Honeytoken accessed (1) or not (0) |
| `session_time` | int | 10-600 | Session duration in seconds |

## 📊 Output

### Single Prediction Response

```json
{
  "attack_type": "Injection",
  "risk_score": 9,
  "confidence": 0.95,
  "anomaly_score": -0.8234,
  "is_anomaly": true
}
```

### Response Fields

| Field | Range | Description |
|-------|-------|-------------|
| `attack_type` | string | Classification: Normal, BruteForce, Injection, DataExfil, Recon |
| `risk_score` | 1-10 | Threat level (1=low, 10=critical) |
| `confidence` | 0-1 | Prediction confidence (higher=more certain) |
| `anomaly_score` | float | Raw anomaly score (negative=anomalous) |
| `is_anomaly` | bool | Whether flagged as anomalous behavior |

## 🌐 API Endpoints

### 1. **Single Prediction**
```bash
POST /predict
Content-Type: application/json

{
  "failed_logins": 120,
  "request_rate": 50,
  "commands_count": 0,
  "sql_payload": 0,
  "honeytoken_access": 0,
  "session_time": 300
}
```

**Response:** Prediction result

### 2. **Batch Prediction**
```bash
POST /predict-batch
Content-Type: application/json

{
  "logs": [
    {...log1...},
    {...log2...},
    {...log3...}
  ]
}
```

**Response:**
```json
{
  "results": [...],
  "total_processed": 3,
  "high_risk_count": 1
}
```

### 3. **Health Check**
```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "version": "1.0.0"
}
```

### 4. **Get Features Info**
```bash
GET /features
```

Returns feature ranges and order.

## 🧪 Test Cases

The system includes 8 comprehensive test cases:

### 1. SQL Injection
```json
{
  "failed_logins": 2,
  "request_rate": 50,
  "commands_count": 1,
  "sql_payload": 1,
  "honeytoken_access": 0,
  "session_time": 120
}
```
**Expected:** Injection attack, High risk score

### 2. Brute Force
```json
{
  "failed_logins": 120,
  "request_rate": 200,
  "commands_count": 0,
  "sql_payload": 0,
  "honeytoken_access": 0,
  "session_time": 600
}
```
**Expected:** BruteForce attack, High risk score

### 3. Reconnaissance
```json
{
  "failed_logins": 5,
  "request_rate": 550,
  "commands_count": 2,
  "sql_payload": 0,
  "honeytoken_access": 0,
  "session_time": 180
}
```
**Expected:** Recon attack, Medium-high risk

### 4. Data Exfiltration (Honeytoken)
```json
{
  "failed_logins": 0,
  "request_rate": 100,
  "commands_count": 15,
  "sql_payload": 0,
  "honeytoken_access": 1,
  "session_time": 450
}
```
**Expected:** DataExfil attack, High risk score

### 5. Normal Traffic
```json
{
  "failed_logins": 1,
  "request_rate": 50,
  "commands_count": 3,
  "sql_payload": 0,
  "honeytoken_access": 0,
  "session_time": 300
}
```
**Expected:** Normal activity, Low risk score

### 6-8. Edge Cases
- Maximum values (all features at max) → Injection, Highest risk
- Minimum values (all features at min) → Normal, Lowest risk
- Complex attack (multiple vectors) → Highest priority detected

## 📡 Testing with curl

### Health Check
```bash
curl http://localhost:8000/health
```

### Single Prediction (Brute Force)
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "failed_logins": 120,
    "request_rate": 200,
    "commands_count": 0,
    "sql_payload": 0,
    "honeytoken_access": 0,
    "session_time": 600
  }'
```

### Single Prediction (SQL Injection)
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "failed_logins": 2,
    "request_rate": 50,
    "commands_count": 1,
    "sql_payload": 1,
    "honeytoken_access": 0,
    "session_time": 120
  }'
```

### API Documentation
```bash
# Swagger UI
http://localhost:8000/docs

# ReDoc
http://localhost:8000/redoc
```

## 🎯 Model Details

### RandomForest Classifier
- **Purpose:** Attack type classification
- **Estimators:** 100 trees
- **Max Depth:** 15
- **Classes:** Normal, BruteForce, Injection, DataExfil, Recon
- **Training/Test Split:** 80/20

### IsolationForest Anomaly Detector
- **Purpose:** Detect unusual behaviors
- **Contamination:** 10% (assumes 10% anomalies)
- **Estimators:** 100 trees

### Risk Score Calculation
```
Risk Score = (Anomaly_Risk × 0.4 + Confidence_Risk × 0.6) × Attack_Multiplier

Where:
- Anomaly_Risk ∈ [0, 5]
- Confidence_Risk ∈ [0, 5]
- Attack_Multiplier varies by type:
  • Injection: 1.3 (most dangerous)
  • DataExfil: 1.2
  • BruteForce: 1.1
  • Recon: 0.9
  • Normal: 0.3 (least risky)

Final Score ∈ [1, 10] (rounded integer)
```

## 📈 Performance Expectations

- **Prediction Latency:** <10ms per log
- **Batch Processing:** ~1-2ms per log
- **Model Size:** ~2-5MB (all .pkl files)
- **Memory Usage:** ~100-200MB (models + API)

## 🔒 Security Considerations

1. **Input Validation:** All inputs are validated and bounded
2. **Model Integrity:** Models should be kept secure and version-controlled
3. **API Rate Limiting:** Consider adding rate limits in production
4. **Logging:** Log all predictions for audit trails
5. **Model Updates:** Retrain periodically with new data

## 🛠️ Troubleshooting

### Models not found error
```
Make sure you've run: python train_model.py
```

### Port already in use
```
lsof -i :8000  # Find process using port 8000
kill -9 <PID>  # Kill the process
```

### ImportError for modules
```
pip install -r requirements.txt
# Or install specific package:
pip install pandas scikit-learn numpy fastapi uvicorn joblib
```

### Poor prediction accuracy
- Regenerate dataset: `python dataset_generator.py`
- Retrain model: `python train_model.py`
- Check input feature ranges are within bounds

## 📚 Integration Examples

### Python
```python
from predict import AttackPredictor

predictor = AttackPredictor('.')

log = {
    'failed_logins': 120,
    'request_rate': 200,
    'commands_count': 0,
    'sql_payload': 0,
    'honeytoken_access': 0,
    'session_time': 600
}

result = predictor.predict(log)
print(f"Attack: {result['attack_type']}, Risk: {result['risk_score']}/10")
```

### JavaScript/Node.js
```javascript
const axios = require('axios');

const log = {
  failed_logins: 120,
  request_rate: 200,
  commands_count: 0,
  sql_payload: 0,
  honeytoken_access: 0,
  session_time: 600
};

axios.post('http://localhost:8000/predict', log)
  .then(response => {
    console.log(`Attack: ${response.data.attack_type}`);
    console.log(`Risk Score: ${response.data.risk_score}/10`);
  });
```

## 📝 Next Steps

1. ✅ Run `python dataset_generator.py` - Generate training data
2. ✅ Run `python train_model.py` - Train models
3. ✅ Run `python test_cases.py` - Test locally
4. ✅ Run `python ml_api.py` - Start API
5. ✅ Run `python test_cases.py api` - Test API endpoints
6. 🔄 Integrate into your backend/SIEM system
7. 📊 Monitor predictions in production
8. 🔄 Retrain models periodically with new data

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the test cases for examples
3. Check API documentation at `/docs`
4. Review code comments in each module

---

**Version:** 1.0.0  
**Status:** Production Ready  
**Last Updated:** 2026-02-03
