"""
Backend README
Complete backend API documentation
"""

# Decoyvers Backend API v2.0

Complete FastAPI backend for multi-node cyber deception platform.

## Features

✅ User Authentication (JWT + bcrypt)  
✅ Multi-node Management (CRUD + API keys)  
✅ Honeypot Log Ingestion  
✅ Agent Event Tracking  
✅ ML-Powered Threat Detection  
✅ User-Scoped Dashboards  
✅ MongoDB Integration  
✅ Production Security  

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Development (demo mode)
export AUTH_ENABLED="False"

# Production (with auth)
export AUTH_ENABLED="True"
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/decoyvers"
export ML_API_URL="http://localhost:8000"
```

### 3. Run Backend

```bash
python main.py
```

Server starts on http://0.0.0.0:8001

## API Documentation

Visit http://localhost:8001/docs for interactive Swagger UI

## Architecture

```
backend/
├── config.py           - All configuration
├── main.py             - FastAPI app
├── models/
│   └── log_models.py   - Pydantic models
├── routes/
│   ├── auth.py         - /auth/register, /auth/login
│   ├── nodes.py        - Node CRUD
│   ├── honeypot.py     - Log ingestion
│   ├── agent.py        - Event ingestion
│   └── alerts.py       - Dashboard
├── services/
│   ├── db_service.py   - MongoDB ops
│   ├── ml_service.py   - ML API
│   ├── auth_service.py - JWT/bcrypt
│   └── node_service.py - Node utils
└── requirements.txt    - Dependencies
```

## Authentication

### Demo Mode
```bash
export AUTH_ENABLED="False"
# No credentials required, auto-uses demo-user
```

### Production Mode
```bash
export AUTH_ENABLED="True"
export JWT_SECRET_KEY="your-secret-key"

# Register user
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123"}'

# Login
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123"}'

# Use token
curl -X GET http://localhost:8001/api/stats \
  -H "Authorization: Bearer <access_token>"
```

## Node Management

Create a node (returns api_key):
```bash
curl -X POST http://localhost:8001/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Honeypot"}'
```

Send honeypot log:
```bash
curl -X POST http://localhost:8001/api/honeypot-log \
  -H "X-Node-Key: nk_..." \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-abc123",
    "service": "SSH",
    "source_ip": "192.168.1.100",
    "activity": "login_attempt",
    "payload": "root:password",
    "timestamp": "2024-01-15T10:00:00"
  }'
```

## Database

MongoDB collections:
- `users` - User accounts
- `nodes` - Deployed nodes
- `decoys` - Honeytoken tracking
- `honeypot_logs` - Honeypot events
- `agent_events` - Agent events
- `alerts` - High-risk alerts
- `attacker_profiles` - Threat intelligence

## Endpoints

### Auth
- `POST /auth/register` - Register user
- `POST /auth/login` - Login user

### Nodes
- `POST /nodes` - Create node
- `GET /nodes` - List nodes
- `PATCH /nodes/{id}` - Update status
- `DELETE /nodes/{id}` - Delete node
- `GET /nodes/{id}/decoys` - Get decoys

### Logs
- `POST /api/honeypot-log` - Honeypot logs
- `POST /api/agent-alert` - Agent events

### Dashboard
- `GET /api/stats` - Statistics
- `GET /api/recent-attacks` - Recent attacks
- `GET /api/alerts` - All alerts
- `GET /api/attacker-profile/{ip}` - Attacker profile
- `GET /api/health` - Health check

## Security Features

✅ JWT authentication with 7-day expiry  
✅ Bcrypt password hashing (salt rounds: 12)  
✅ Node API keys for distributed auth  
✅ User-scoped data isolation  
✅ Input validation (max_length limits)  
✅ MongoDB indexes for performance  
✅ ML service timeout + fallback  
✅ Error handling and logging  

## Deployment

### Render.com

```yaml
services:
  - type: web
    name: decoyvers-backend
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: MONGODB_URI
        scope: run
      - key: JWT_SECRET_KEY
        scope: run
      - key: AUTH_ENABLED
        value: "True"
```

### Docker

```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r backend/requirements.txt
CMD ["python", "backend/main.py"]
```

## Troubleshooting

**MongoDB connection failed:**
- Check MONGODB_URI is correct
- Ensure network access is allowed

**JWT error:**
- Set JWT_SECRET_KEY in environment
- Use secrets.token_urlsafe(32) to generate

**ML API timeout:**
- Backend has 3-second timeout with fallback
- Check ML service is running on correct port

## Support

For issues, check logs with:
```bash
tail -f logs/backend.log
```
