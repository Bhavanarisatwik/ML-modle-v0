# Deployment Guide - DecoyVerse Platform v2.0

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│         Frontend (Vercel)                    │
│  React 19 + TypeScript + Vite               │
│  Dashboard, Node Management, Alerts         │
└──────────────────┬──────────────────────────┘
                   │ HTTPS
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│ Backend (Render) │   │ ML Service       │
│ FastAPI          │   │ (Render)         │
│ Port 10000       │   │ FastAPI          │
│                  │   │ Port 10000       │
│ ✓ Auth           │   │                  │
│ ✓ Node Mgmt      │   │ ✓ Predictions    │
│ ✓ Log Ingestion  │   │ ✓ Risk Scoring   │
│ ✓ Alerts         │   │ ✓ Anomaly       │
│ ✓ Dashboard      │   │   Detection     │
└────────┬─────────┘   └──────┬───────────┘
         │                    │
         │ HTTP Client        │ HTTP Client
         │ (joblib models)    │ (ML API)
         └────────┬───────────┘
                  │
                  ▼
        ┌──────────────────┐
        │ MongoDB Atlas    │
        │ Cloud Database   │
        │                  │
        │ ✓ Users          │
        │ ✓ Nodes          │
        │ ✓ Logs           │
        │ ✓ Alerts         │
        │ ✓ Profiles       │
        └──────────────────┘
```

---

## Prerequisites

- MongoDB Atlas cluster (free tier OK)
- Render account (free tier OK for testing)
- GitHub repo with both `backend/` and `ml_service/` folders
- Git configured locally

---

## Step 1: Git Setup & Push

### Verify Folder Structure

```
your-repo/
├── backend/
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   ├── models/
│   ├── routes/
│   └── services/
└── ml_service/
    ├── ml_api.py
    ├── predict.py
    ├── feature_extractor.py
    ├── classifier.pkl
    ├── anomaly_model.pkl
    ├── scaler.pkl
    ├── label_encoder.pkl
    ├── feature_columns.pkl
    ├── requirements.txt
    ├── Procfile
    └── runtime.txt
```

### Commit & Push

```bash
git add .
git commit -m "Add backend and ML microservice"
git push origin main
```

---

## Step 2: Deploy Backend Service (Render)

### Create Web Service

1. Go to [render.com](https://render.com)
2. Click **New +** → **Web Service**
3. Connect your GitHub repo
4. Fill in:

| Field | Value |
|-------|-------|
| **Name** | `decoyvers-backend` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port 10000` |

### Add Environment Variables

Click **Environment** and add:

```
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/decoyvers?retryWrites=true&w=majority
ML_API_URL=https://decoyvers-ml.onrender.com/predict
AUTH_ENABLED=False
JWT_SECRET_KEY=your-random-secret-key-here
```

> **Note:** Leave `ML_API_URL` placeholder for now. Update after ML service deploys.

### Deploy

Click **Create Web Service**. Wait for build to complete.

**You'll get:** `https://decoyvers-backend.onrender.com`

Test it:
```bash
curl https://decoyvers-backend.onrender.com/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "model_loaded": false,
  "version": "1.0.0"
}
```

---

## Step 3: Deploy ML Service (Render)

### Create Second Web Service

1. Click **New +** → **Web Service** again
2. **Same GitHub repo**, same branch
3. Fill in:

| Field | Value |
|-------|-------|
| **Name** | `decoyvers-ml` |
| **Root Directory** | `ml_service` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn ml_api:app --host 0.0.0.0 --port 10000` |

### No Environment Variables Needed

(Models load from disk)

### Deploy

Click **Create Web Service**. Wait for build.

**You'll get:** `https://decoyvers-ml.onrender.com`

Test it:
```bash
curl -X POST https://decoyvers-ml.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "failed_logins": 85,
    "request_rate": 450,
    "commands_count": 8,
    "sql_payload": 1,
    "honeytoken_access": 0,
    "session_time": 300
  }'
```

Expected response:
```json
{
  "attack_type": "Injection",
  "risk_score": 9,
  "confidence": 0.95,
  "anomaly_score": -0.8234,
  "is_anomaly": true
}
```

---

## Step 4: Connect Backend to ML Service

### Update Backend Environment Variables

1. Go to **decoyvers-backend** service on Render
2. Click **Environment**
3. Update `ML_API_URL`:
   ```
   ML_API_URL=https://decoyvers-ml.onrender.com/predict
   ```
4. Click **Save**
5. Render auto-redeploys

---

## Step 5: Test Full Pipeline

### Health Check
```bash
curl https://decoyvers-backend.onrender.com/api/health
```

### Create Node (Demo Mode)
```bash
curl -X POST https://decoyvers-backend.onrender.com/nodes \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Node"}'
```

Response includes `node_api_key` - **save this!**

### Send Honeypot Log
```bash
curl -X POST https://decoyvers-backend.onrender.com/api/honeypot-log \
  -H "Content-Type: application/json" \
  -H "X-Node-Id: node-abc123" \
  -H "X-Node-Key: nk_your-api-key" \
  -d '{
    "service": "SSH",
    "source_ip": "192.168.1.100",
    "activity": "login_attempt",
    "payload": "{\"username\": \"admin\", \"password\": \"wrong\"}",
    "timestamp": "2026-02-04T10:30:00Z",
    "node_id": "node-abc123"
  }'
```

### View Alerts
```bash
curl https://decoyvers-backend.onrender.com/api/stats
```

---

## Step 6: Connect Frontend

Update frontend config:

**`src/api/client.ts` or `.env.production`:**
```
VITE_API_URL=https://decoyvers-backend.onrender.com/api
```

Redeploy frontend to Vercel.

---

## Troubleshooting

### Backend Build Fails
```
ERROR: dependencies could not be resolved
```
✅ **Solution:** Check `backend/requirements.txt` versions

### ML Service Takes Long to Load
```
Model loading...
```
✅ **Normal on first startup.** Models cache in memory after first request.

### 401 Unauthorized on /nodes
```
"detail": "Unauthorized"
```
✅ **Solution:** Set `AUTH_ENABLED=False` in backend env vars (demo mode)

### ML Service Returns 500
```
"detail": "Model not loaded"
```
✅ **Check:** Ensure `classifier.pkl`, `scaler.pkl` exist in ml_service/

### Database Connection Failed
```
ERROR: MongoDB connection failed
```
✅ **Check:** 
- MONGODB_URI is correct
- IP whitelist in MongoDB Atlas includes 0.0.0.0

---

## Production Checklist

- [ ] Set `AUTH_ENABLED=True` and strong `JWT_SECRET_KEY`
- [ ] Enable IP whitelist in MongoDB Atlas (don't use 0.0.0.0)
- [ ] Use production database (separate from testing)
- [ ] Set CORS_ORIGINS to your frontend domain
- [ ] Enable SSL/TLS (automatic on Render)
- [ ] Monitor backend logs on Render dashboard
- [ ] Set up Render alerts for failed deploys
- [ ] Backup MongoDB Atlas regularly

---

## Architecture Complete ✅

You now have:

✔ **SaaS Backend** - User auth, node management, multi-tenant
✔ **ML Microservice** - Attack detection, risk scoring, anomaly detection  
✔ **Cloud Database** - MongoDB Atlas for persistence
✔ **Agent System** - Honeypot + endpoint agent integration
✔ **Dashboard** - Real-time alerts, threat intelligence
✔ **Production Ready** - Scalable, cloud-native architecture

This is **industry-level architecture**, just optimized for prototype scale.

---

## Next Steps (Optional)

- **User Onboarding:** Create signup flow → auto-generate JWT
- **Agent Auto-Registration:** Agents self-register with backend
- **Webhook Alerts:** Send alerts to Slack/Teams
- **API Rate Limiting:** Protect against abuse
- **Refresh Tokens:** Longer session management
- **Audit Logging:** Track all API calls
