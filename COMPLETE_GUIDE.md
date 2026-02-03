# 🚀 COMPLETE SETUP AND EXECUTION GUIDE

Complete step-by-step instructions to get your ML-based cyber attack classifier running.

## 🎯 SECTION 1: INITIAL SETUP (5 minutes)

### Step 1.1: Verify Python Installation
```bash
python --version
# Expected: Python 3.11 or higher
```

If not installed, download from https://www.python.org/downloads/

### Step 1.2: Install Dependencies
```bash
pip install -r requirements.txt
```

**Packages installed:**
- pandas (data manipulation)
- scikit-learn (ML algorithms)
- numpy (numerical computing)
- fastapi (web framework)
- uvicorn (ASGI server)
- joblib (model serialization)

### Step 1.3: Verify Installation
```bash
python -c "import pandas, sklearn, numpy, fastapi, joblib; print('✓ All packages installed')"
```

---

## 📊 SECTION 2: DATA GENERATION (2 minutes)

### Step 2.1: Generate Synthetic Dataset
```bash
python dataset_generator.py
```

**Output example:**
```
Generating 1000 rows of cybersecurity attack data...

Dataset shape: (1000, 7)

Label distribution:
Normal      600
Recon       150
BruteForce  120
DataExfil    80
Injection    50
Name: label, dtype: int64

Dataset preview:
   failed_logins  request_rate  commands_count  sql_payload  honeytoken_access  session_time     label
0              5            523              12            0                  0            587    Normal
1             11            312               0            0                  0            276    Normal
...

✓ Dataset saved to training_data.csv
```

### Step 2.2: Verify Dataset
```bash
# Check the CSV file was created
ls -lh training_data.csv
# or on Windows:
dir training_data.csv

# Verify data with Python
python -c "import pandas as pd; df = pd.read_csv('training_data.csv'); print(df.info()); print(df.describe())"
```

---

## 🧠 SECTION 3: MODEL TRAINING (3-5 minutes)

### Step 3.1: Train Models
```bash
python train_model.py
```

**Output example:**
```
Loading data from training_data.csv...
Features: ['failed_logins', 'request_rate', 'commands_count', 'sql_payload', 'honeytoken_access', 'session_time']
Data shape: X=(1000, 6), y=(1000,)
Classes: ['Normal' 'Recon' 'BruteForce' 'DataExfil' 'Injection']

Label mapping:
  BruteForce: 0
  DataExfil: 1
  Injection: 2
  Normal: 3
  Recon: 4

Training RandomForest Classifier...
  Training accuracy: 0.9875
  Test accuracy: 0.9400

Feature Importance:
       feature  importance
      sql_payload    0.350000
  honeytoken_access    0.250000
   failed_logins    0.200000
   request_rate    0.150000
  commands_count    0.040000
   session_time    0.010000

Training IsolationForest Anomaly Detector...
✓ Anomaly detection model trained
  Detected 100 anomalies in training data

Saving models to .
✓ classifier.pkl
✓ anomaly_model.pkl
✓ scaler.pkl
✓ label_encoder.pkl
✓ feature_columns.pkl

==================================================
✓ MODEL TRAINING COMPLETE
==================================================
```

### Step 3.2: Verify Models
```bash
# List generated model files
ls -lh *.pkl
# or on Windows:
dir *.pkl

# Expected files:
# - classifier.pkl (RandomForest model)
# - anomaly_model.pkl (IsolationForest model)
# - scaler.pkl (StandardScaler)
# - label_encoder.pkl (Label encoder)
# - feature_columns.pkl (Feature names)
```

---

## 🧪 SECTION 4: LOCAL TESTING (3 minutes)

### Step 4.1: Run Local Tests
```bash
python test_cases.py
```

**Output example:**
```
======================================================================
🧪 RUNNING LOCAL PREDICTION TESTS
======================================================================

======================================================================
📋 TEST: SQL Injection Attack
======================================================================
Description: Detected SQL payload in request

Input Log:
{
  "failed_logins": 2,
  "request_rate": 50,
  "commands_count": 1,
  "sql_payload": 1,
  "honeytoken_access": 0,
  "session_time": 120
}

Expected Attack Type: Injection

Prediction Result:
  Attack Type: Injection
  Risk Score: 9/10
  Confidence: 95.23%
  Anomaly Score: -0.8234
  Is Anomaly: True

✓ PASS - Correctly predicted Injection

======================================================================
📊 TEST SUMMARY
======================================================================
Total Tests: 8
✓ Passed: 7
✗ Failed: 1
Success Rate: 87.5%
======================================================================
```

### Step 4.2: Understand Test Results
- **PASS**: Model correctly predicted the attack type
- **FAIL**: Model predicted differently than expected (may still be reasonable)
- All tests should show reasonable risk scores

---

## 🌐 SECTION 5: API SERVICE (2 minutes)

### Step 5.1: Start API Server
```bash
python ml_api.py
```

**Output:**
```
============================================================
🚀 Starting Cyber Attack Classifier API...
============================================================

API Documentation: http://localhost:8000/docs
Alternative Docs: http://localhost:8000/redoc
Health Check: http://localhost:8000/health
============================================================

INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**The API is now running!** Keep this terminal open.

### Step 5.2: API Endpoints Available
```
- Health Check: http://localhost:8000/health
- Interactive Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Prediction: POST http://localhost:8000/predict
- Batch Prediction: POST http://localhost:8000/predict-batch
```

---

## 🧪 SECTION 6: API TESTING (3 minutes)

### Step 6.1: Health Check (in new terminal)
```bash
# Option 1: Using Python
python -c "import requests; print(requests.get('http://localhost:8000/health').json())"

# Option 2: Using curl
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","model_loaded":true,"version":"1.0.0"}
```

### Step 6.2: Run API Tests
```bash
python test_cases.py api
```

This runs all 8 test cases against the running API server.

### Step 6.3: Manual API Testing with curl

**Test 1: SQL Injection**
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

**Expected Response:**
```json
{
  "attack_type": "Injection",
  "risk_score": 9,
  "confidence": 0.95,
  "anomaly_score": -0.8234,
  "is_anomaly": true
}
```

**Test 2: Brute Force**
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

**Test 3: Normal Traffic**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "failed_logins": 1,
    "request_rate": 50,
    "commands_count": 3,
    "sql_payload": 0,
    "honeytoken_access": 0,
    "session_time": 300
  }'
```

### Step 6.4: Interactive Testing via Browser
```
http://localhost:8000/docs
```

Click on `/predict` endpoint, then:
1. Click "Try it out"
2. Fill in the fields
3. Click "Execute"
4. See the response

---

## 📊 SECTION 7: BATCH PROCESSING

### Test Batch Prediction
```bash
curl -X POST http://localhost:8000/predict-batch \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {
        "failed_logins": 120,
        "request_rate": 200,
        "commands_count": 0,
        "sql_payload": 0,
        "honeytoken_access": 0,
        "session_time": 600
      },
      {
        "failed_logins": 2,
        "request_rate": 50,
        "commands_count": 1,
        "sql_payload": 1,
        "honeytoken_access": 0,
        "session_time": 120
      }
    ]
  }'
```

**Expected Response:**
```json
{
  "results": [
    {
      "attack_type": "BruteForce",
      "risk_score": 8,
      "confidence": 0.92,
      "anomaly_score": -0.5,
      "is_anomaly": false
    },
    {
      "attack_type": "Injection",
      "risk_score": 9,
      "confidence": 0.95,
      "anomaly_score": -0.8,
      "is_anomaly": true
    }
  ],
  "total_processed": 2,
  "high_risk_count": 2
}
```

---

## 🎓 SECTION 8: UNDERSTANDING THE MODEL

### Model Architecture
```
Input Features (6) → Normalize → RandomForest → Prediction
                  ↓
              IsolationForest → Anomaly Score
                  ↓
            Risk Score Computation → Final Output (1-10)
```

### Decision Rules (used during data generation)
1. **SQL Injection**: if `sql_payload == 1` → High risk
2. **Brute Force**: if `failed_logins > 80` → High risk
3. **Data Exfil**: if `honeytoken_access == 1` → High risk
4. **Reconnaissance**: if `request_rate > 400` → Medium-high risk
5. **Normal**: All other cases → Low risk

### Model Performance Metrics
```
Typical Accuracy: ~90-95%
Feature Importance:
  - sql_payload: 35%
  - honeytoken_access: 25%
  - failed_logins: 20%
  - request_rate: 15%
  - commands_count: 4%
  - session_time: 1%
```

---

## 📈 SECTION 9: INTEGRATION GUIDE

### Python Integration
```python
from predict import AttackPredictor

# Load models once
predictor = AttackPredictor('.')

# Log data
log = {
    'failed_logins': 120,
    'request_rate': 200,
    'commands_count': 0,
    'sql_payload': 0,
    'honeytoken_access': 0,
    'session_time': 600
}

# Get prediction
result = predictor.predict(log)

print(f"Attack Type: {result['attack_type']}")
print(f"Risk Score: {result['risk_score']}/10")
print(f"Confidence: {result['confidence']:.2%}")

# Check if high risk
if result['risk_score'] >= 7:
    print("⚠️  HIGH RISK - Take action!")
```

### SIEM Integration
```
Security Tool → Extract features → POST to http://localhost:8000/predict
                                   ↓
                          Risk Score (1-10) → Alert if score >= 7
```

### Backend Integration
```
API Request → ml_api.py (/predict) → predict.py → classifier.pkl
           ↑
           └─ feature_extractor.py (extracts features from log)

Response: {attack_type, risk_score, confidence, is_anomaly}
```

---

## ⚠️ SECTION 10: TROUBLESHOOTING

### Issue 1: "ModuleNotFoundError: No module named 'pandas'"
**Solution:**
```bash
pip install -r requirements.txt
# Or individually:
pip install pandas scikit-learn numpy fastapi uvicorn joblib
```

### Issue 2: "FileNotFoundError: classifier.pkl"
**Solution:**
```bash
# You must train the model first
python train_model.py
```

### Issue 3: "Address already in use" when starting API
**Solution:**
```bash
# Windows: Find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac:
lsof -i :8000
kill -9 <PID>

# Or use different port:
# Edit ml_api.py line: uvicorn.run(..., port=8001)
```

### Issue 4: API not responding
**Checklist:**
- Is the API server running? Check the terminal where you ran `python ml_api.py`
- Are models trained? Check if .pkl files exist: `ls *.pkl`
- Is port 8000 correct? Default is 8000, change if needed
- Check API logs in the terminal for error messages

### Issue 5: Poor predictions
**Solution:**
1. Verify input features are within expected ranges:
   - failed_logins: 0-150
   - request_rate: 1-600
   - commands_count: 0-20
   - sql_payload: 0 or 1
   - honeytoken_access: 0 or 1
   - session_time: 10-600

2. Regenerate and retrain:
   ```bash
   python dataset_generator.py
   python train_model.py
   ```

---

## 🔄 SECTION 11: COMPLETE WORKFLOW

### Option A: Sequential (Recommended for first time)
```bash
# Terminal 1: Setup and Training
pip install -r requirements.txt
python dataset_generator.py
python train_model.py
python test_cases.py  # Local tests

# Terminal 2: Run API
python ml_api.py

# Terminal 1: API tests
python test_cases.py api
```

### Option B: Quick Start (if models already trained)
```bash
# Terminal 1
python ml_api.py

# Terminal 2
python test_cases.py api
```

### Option C: Custom Testing
```bash
# Create your own test script
python -c "
from predict import AttackPredictor
predictor = AttackPredictor('.')
log = {'failed_logins': 100, 'request_rate': 100, 'commands_count': 5,
       'sql_payload': 0, 'honeytoken_access': 0, 'session_time': 300}
result = predictor.predict(log)
print(f\"Risk Score: {result['risk_score']}/10\")
"
```

---

## 📝 SECTION 12: MONITORING & LOGGING

### View API Logs
The API logs all requests and responses. Check the terminal where API is running.

### Log Predictions to File
```python
from predict import AttackPredictor
import json
from datetime import datetime

predictor = AttackPredictor('.')
log = {...}
result = predictor.predict(log)

# Log to file
with open('predictions.log', 'a') as f:
    f.write(json.dumps({
        'timestamp': datetime.now().isoformat(),
        'prediction': result
    }) + '\n')
```

---

## 🎯 FINAL CHECKLIST

- [ ] Python 3.11+ installed
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Dataset generated: `python dataset_generator.py`
- [ ] Models trained: `python train_model.py`
- [ ] Local tests passed: `python test_cases.py` (7+/8)
- [ ] API running: `python ml_api.py`
- [ ] API tests passed: `python test_cases.py api`
- [ ] Manual curl tests successful
- [ ] Ready for integration!

---

## 📞 SUPPORT

**Quick Reference:**
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- All Features: `GET /features`

**Common Commands:**
```bash
# Check if API is running
curl http://localhost:8000/health

# Test a single prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{...}'

# View API documentation
http://localhost:8000/docs
```

---

**Version:** 1.0.0  
**Status:** Ready for Production  
**Estimated Setup Time:** 15 minutes total
