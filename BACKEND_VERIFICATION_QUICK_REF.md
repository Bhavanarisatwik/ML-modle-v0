# Backend Verification - Quick Reference Guide

**Status**: ✅ VERIFIED  
**Date**: February 4, 2026

---

## 🚀 Quick Summary

The backend implements **three-layer data security**:

```
Layer 1: JWT Authentication  → Extract user_id from token
Layer 2: Node Authorization  → Verify user owns the node
Layer 3: Query Scoping       → Filter data by user's nodes
```

---

## 📡 All Endpoints at a Glance

### Decoys
| Endpoint | Purpose | Scope | Query |
|----------|---------|-------|-------|
| `GET /api/decoys` | All user decoys | User | `node_id ∈ user_nodes` |
| `GET /api/decoys/node/{id}` | Node decoys | Node | `node_id = id` + auth check |

### Honeytokels
| Endpoint | Purpose | Scope | Query |
|----------|---------|-------|-------|
| `GET /api/honeytokels` | All user honeytokels | User | `node_id ∈ user_nodes, type="honeytoken"` |
| `GET /api/honeytokels/node/{id}` | Node honeytokels | Node | `node_id = id, type="honeytoken"` + auth check |

### Events/Logs
| Endpoint | Purpose | Scope | Query |
|----------|---------|-------|-------|
| `GET /api/logs` | All user events | User | `node_id ∈ user_nodes` (combined from 2 collections) |
| `GET /api/logs/node/{id}` | Node events | Node | `node_id = id` + auth check |

### Alerts & Stats
| Endpoint | Purpose | Scope | Query |
|----------|---------|-------|-------|
| `GET /api/stats` | Dashboard stats | User | Aggregation pipelines by user_id |
| `GET /api/recent-attacks` | Recent alerts | User | Sorted by timestamp, user_id filtered |
| `GET /api/alerts` | All alerts | User | user_id filtered + optional filters |

---

## 🔐 Authorization Pattern

### User-Scoped Endpoints
```python
# 1. Extract user_id from JWT
user_id = get_user_id_from_header(authorization)

# 2. Get user's nodes
nodes = await db_service.get_nodes_by_user(user_id)
node_ids = [n["node_id"] for n in nodes]

# 3. Query with node filter
data = await db_service.get_data_for_nodes(node_ids, limit)

# Result: Only user's data
```

### Node-Specific Endpoints
```python
# 1. Extract user_id from JWT
user_id = get_user_id_from_header(authorization)

# 2. VERIFY NODE OWNERSHIP
node = await db_service.get_node_by_id(node_id)
if not node or node.user_id != user_id:
    raise HTTPException(403, "Unauthorized")  # ← Security check!

# 3. Query specific node
data = await db_service.get_data_for_node(node_id)

# Result: Only if user owns the node
```

---

## 💾 Database Queries

### Get User's Data
```python
# Method 1: List endpoints (all user's nodes)
node_ids = [n.node_id for n in user_nodes]
db.collection.find({"node_id": {"$in": node_ids}})

# Method 2: Single node (after auth check)
db.collection.find({"node_id": node_id})
```

### Aggregations (Stats)
```javascript
// Unique attackers
db.alerts.aggregate([
  {$match: {user_id: "user_123"}},
  {$group: {_id: "$source_ip"}}
])

// Average risk score
db.alerts.aggregate([
  {$match: {user_id: "user_123"}},
  {$group: {
    _id: null,
    avg: {$avg: "$risk_score"},
    high_risk: {$sum: {$cond: [{$gte: ["$risk_score", 70]}, 1, 0]}}
  }}
])
```

---

## ✅ Data Isolation Verification

| Scenario | Result |
|----------|--------|
| User1 requests own nodes | ✓ Gets their data |
| User1 requests User2's node | ✓ Gets 403 Forbidden |
| User1 requests non-existent node | ✓ Gets 403 Forbidden |
| User with no nodes | ✓ Gets empty list |

---

## 🐛 Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Missing data | Wrong node_id in request | Verify node_id matches user's nodes |
| 403 error | Requesting node you don't own | Use correct node_id for your user |
| Empty response | No events for node | Check if node has any events |
| Slow query | Large limit value | Reduce limit parameter |

---

## 📋 Response Examples

### Decoy Response
```json
{
  "id": "507f1f77bcf86cd799439011",
  "node_id": "node_001",
  "type": "file",
  "status": "active",
  "triggers_count": 5,
  "last_triggered": "2026-02-04T10:00:00Z",
  "port": null,
  "file_name": "sensitive_data.txt"
}
```

### Event Response
```json
{
  "id": "507f1f77bcf86cd799439012",
  "timestamp": "2026-02-04T10:00:00Z",
  "node_id": "node_001",
  "event_type": "SSH login attempt",
  "source_ip": "192.168.1.100",
  "severity": "critical",
  "related_decoy": "admin_creds.json",
  "risk_score": 85
}
```

### Stats Response
```json
{
  "total_attacks": 42,
  "active_alerts": 12,
  "unique_attackers": 8,
  "avg_risk_score": 65.5,
  "high_risk_count": 6,
  "total_nodes": 3,
  "active_nodes": 2,
  "recent_risk_average": 72.3
}
```

---

## 🎯 Filter Parameters

### Logs Endpoint
```http
GET /api/logs?limit=100&node_id=node_001&severity=critical&search=192.168.1.1
```

Parameters:
- `limit`: Max results (default 100)
- `node_id`: Filter by specific node
- `severity`: low, medium, high, critical
- `search`: Search in source_ip, event_type, file_accessed

### Alerts Endpoint
```http
GET /api/alerts?limit=50&severity=critical&status=open
```

Parameters:
- `limit`: Max results (default 50)
- `severity`: critical, high, medium, low
- `status`: open, investigating, resolved

---

## 🔄 Data Flow Summary

```
Frontend Request
    ↓
Authorization Header → Extract JWT → Get user_id
    ↓
(If node-specific) Verify node ownership
    ↓
Get user's node_ids
    ↓
Query MongoDB with node_id filter
    ↓
Normalize response
    ↓
Return to Frontend
```

---

## 📞 Support Reference

| Issue | File | Solution |
|-------|------|----------|
| Route not responding | `backend/routes/*.py` | Check route definition |
| Data not filtering correctly | `backend/services/db_service.py` | Verify query logic |
| Authorization errors | `backend/routes/*.py` | Check node ownership verification |
| Authentication fails | `backend/middleware/auth.py` | Verify JWT token |
| Slow queries | `backend/config.py` | Check MongoDB indexes |

---

## 🚀 Deployment Checklist

- [ ] All endpoints returning correct node-wise data
- [ ] Authorization checks working (403 on unauthorized)
- [ ] Response times acceptable
- [ ] Database indexes on node_id, user_id, timestamp
- [ ] JWT token validation enabled
- [ ] Error handling in place
- [ ] Logging configured

---

## 📚 Full Documentation

For detailed information, see:
1. **BACKEND_NODE_WISE_VERIFICATION.md** - Comprehensive endpoint docs
2. **BACKEND_DATA_PIPELINE_VISUAL.md** - Visual architecture & flows
3. **TECHNICAL_DEEP_DIVE.md** - Database queries & aggregations

---

**Status**: ✅ All Systems Operational  
**Last Verified**: February 4, 2026  
**Next Steps**: Deploy with confidence
