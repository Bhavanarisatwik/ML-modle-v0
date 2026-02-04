# ML Retraining Pipeline

## Overview
This pipeline retrains the DecoyVerse ML model using real production logs from MongoDB.

## Files
- `export_real_logs.py` - Exports logs from MongoDB and converts to ML features
- `train_model.py` - Trains RandomForest and IsolationForest models
- `retrain_pipeline.py` - One-command pipeline to run everything
- `predict.py` - Updated with improved risk scoring

## Quick Start

### 1. Install Dependencies
```bash
cd ml_service
pip install pymongo pandas scikit-learn joblib numpy
```

### 2. Run Pipeline
```bash
python retrain_pipeline.py
```

This will:
1. Connect to MongoDB
2. Export honeypot logs and agent events
3. Convert to ML features
4. Auto-label data using rules
5. Train new models
6. Save updated model files

### 3. Deploy
```bash
cd ..
git add .
git commit -m "Retrain ML model with real production data"
git push
```

## Data Labeling Rules

The pipeline auto-labels logs using these rules (priority order):

1. **DataExfil** - Honeytoken access detected
2. **BruteForce** - Failed logins > 50
3. **Injection** - SQL payload detected
4. **Recon** - Request rate > 300
5. **Normal** - Everything else

## Risk Scoring (Updated)

```
risk_score = (confidence × 6) + (anomaly_score × 4)

Bonuses:
+ honeytoken_access: +2 points
+ failed_logins > 50: +1 point

Attack type multipliers:
- DataExfil: 2.0x
- Injection: 1.5x
- BruteForce: 1.2x
- Recon: 0.8x
- Normal: 0.3x

Final: Clamped to 0-10
```

## Expected Risk Scores

- **Normal traffic**: 0-2
- **Reconnaissance**: 5-7
- **Brute force**: 8-10
- **Honeytoken access**: 9-10
- **SQL injection**: 8-10

## Features Used

```python
FEATURE_ORDER = [
    'failed_logins',      # Number of failed login attempts
    'request_rate',       # Requests per second
    'commands_count',     # Executed commands count
    'sql_payload',        # 1 if SQL injection, 0 otherwise
    'honeytoken_access',  # 1 if honeytoken accessed, 0 otherwise
    'session_time'        # Session duration in seconds
]
```

## Troubleshooting

### No logs in database
Generate test data first:
```bash
curl -X POST https://ml-modle-v0-1.onrender.com/api/honeypot-log \
  -H "Content-Type: application/json" \
  -d '{"service":"SSH", "source_ip":"1.2.3.4", ...}'
```

### MongoDB connection failed
Check environment variable:
```bash
export MONGODB_URI="mongodb+srv://..."
python export_real_logs.py
```

### Imbalanced labels
Normal behavior - security logs are often imbalanced. The RandomForest handles this well.

## Model Files

After retraining, these files are updated:
- `classifier.pkl` - RandomForest attack classifier
- `anomaly_model.pkl` - IsolationForest anomaly detector
- `scaler.pkl` - StandardScaler for anomaly features
- `label_encoder.pkl` - Label encoding mapping
- `feature_columns.pkl` - Feature order metadata

## API Compatibility

✅ API remains unchanged
✅ Same feature order
✅ Same /predict endpoint
✅ Drop-in replacement

No backend changes required!
