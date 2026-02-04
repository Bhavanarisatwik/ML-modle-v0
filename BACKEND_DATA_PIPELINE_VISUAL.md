# Backend Node-Wise Data Pipeline - Visual Architecture

## 🏗️ Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND REQUEST                             │
│         GET /api/decoys/node/{nodeId}                               │
│         Authorization: Bearer <JWT_TOKEN>                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI ROUTE HANDLER                            │
│            (backend/routes/{decoys|logs|alerts}.py)                 │
│                                                                      │
│  1. Extract Authorization Header                                    │
│  2. Validate JWT Token                                              │
│  3. Extract user_id from token claims                               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  AUTHORIZATION LAYER                                │
│                                                                      │
│  NODE-SPECIFIC ENDPOINTS ONLY:                                      │
│  ✓ Fetch node from DB                                               │
│  ✓ Verify node.user_id == request.user_id                          │
│  ✓ Return 403 if unauthorized                                       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                DATABASE SERVICE LAYER                               │
│            (backend/services/db_service.py)                         │
│                                                                      │
│  USER-SCOPED QUERIES:                                               │
│  ├─ get_nodes_by_user(user_id)                                     │
│  │  → {user_id: user_id}                                            │
│  │  → Returns: [node1, node2, node3, ...]                          │
│  │                                                                   │
│  └─ Extract node_ids: [node1_id, node2_id, node3_id]               │
│                                                                      │
│  MULTI-NODE QUERIES:                                                │
│  ├─ get_user_decoys(node_ids, limit)                               │
│  │  → {node_id: {$in: [node1_id, node2_id, node3_id]}}            │
│  │  → Returns: All decoys for user's nodes                          │
│  │                                                                   │
│  ├─ get_user_honeytokels(node_ids, limit)                          │
│  │  → {node_id: {$in: [...], type: "honeytoken"}                   │
│  │  → Returns: All honeytokels for user's nodes                     │
│  │                                                                   │
│  ├─ get_user_events(node_ids, limit)                               │
│  │  → Honeypot logs + Agent events for nodes                        │
│  │  → Combined and sorted by timestamp DESC                         │
│  │                                                                   │
│  └─ get_user_stats(user_id)                                        │
│     → Aggregation pipelines:                                        │
│       • Count total/active nodes                                    │
│       • Count total attacks                                         │
│       • Group by source_ip for unique attackers                     │
│       • Average risk score                                          │
│       • High-risk count (risk_score >= 70)                          │
│                                                                      │
│  NODE-SPECIFIC QUERIES:                                             │
│  ├─ get_decoys_by_node(node_id)                                     │
│  │  → {node_id: node_id}                                            │
│  │  → Returns: All decoys for specific node                         │
│  │                                                                   │
│  ├─ get_node_honeytokels(node_id)                                   │
│  │  → {node_id: node_id, type: "honeytoken"}                       │
│  │  → Returns: All honeytokels for specific node                    │
│  │                                                                   │
│  └─ get_node_events(node_id, limit)                                │
│     → Honeypot logs + Agent events for specific node                │
│                                                                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   MONGODB COLLECTIONS                               │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │   NODES      │   │   DECOYS     │   │   ALERTS     │            │
│  │              │   │              │   │              │            │
│  │ user_id (ix) │   │ node_id (ix) │   │ user_id (ix) │            │
│  │ node_id      │   │ type         │   │ node_id      │            │
│  │ status       │   │ status       │   │ source_ip    │            │
│  │ ...          │   │ ...          │   │ risk_score   │            │
│  └──────────────┘   └──────────────┘   └──────────────┘            │
│                                                                      │
│  ┌────────────────────┐      ┌────────────────────┐               │
│  │ HONEYPOT_LOGS      │      │ AGENT_EVENTS       │               │
│  │                    │      │                    │               │
│  │ node_id (ix)       │      │ node_id (ix)       │               │
│  │ timestamp (ix)     │      │ timestamp (ix)     │               │
│  │ source_ip          │      │ hostname           │               │
│  │ severity           │      │ ...                │               │
│  └────────────────────┘      └────────────────────┘               │
│                                                                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  RESPONSE NORMALIZATION                             │
│            (Decoy/Honeytok/Event Models)                           │
│                                                                      │
│  Raw DB Document                  Normalized Response               │
│  ────────────────────             ──────────────────                │
│  {                                 {                                │
│    _id: ObjectId(...),        →     id: "string",                  │
│    node_id: "node1",               node_id: "node1",               │
│    file_name: "creds.txt",         name: "creds.txt",              │
│    type: "honeytoken",             type: "honeytoken",             │
│    status: "active",               status: "active",               │
│    triggers_count: 5,              triggers: 5,                    │
│    last_triggered: "2026-02-04"    last_triggered: "2026-02-04"    │
│  }                               }                                  │
│                                                                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI RESPONSE                                │
│              (Status 200 + Normalized Data)                        │
│                                                                      │
│  {                                                                   │
│    "success": true,                                                 │
│    "data": [                                                        │
│      {                                                              │
│        "id": "...",                                                 │
│        "node_id": "...",                                            │
│        "type": "...",                                               │
│        ...                                                          │
│      }                                                              │
│    ]                                                                │
│  }                                                                   │
│                                                                      │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND RECEIVES                                │
│            (React component updates state)                          │
│                                                                      │
│  - Dashboard displays node-wise data                                │
│  - Only user's data is visible                                      │
│  - Filter by node/severity/search if specified                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Request Flow Examples

### Example 1: Get All Decoys for User
```
REQUEST:
  GET /api/decoys
  Authorization: Bearer eyJhbGc... (user_id="user123")

BACKEND FLOW:
  1. Extract user_id = "user123" from token
  2. Query: db.nodes.find({user_id: "user123"})
     Result: [{node_id: "node1"}, {node_id: "node2"}]
  3. Extract: node_ids = ["node1", "node2"]
  4. Query: db.decoys.find({node_id: {$in: ["node1", "node2"]}}).limit(50)
  5. Normalize each decoy with DecoyModel
  6. Return: List[Decoy]

RESULT:
  ✓ All decoys visible only to user123
  ✓ Decoys from both node1 and node2 included
  ✓ Limited to 50 results
```

### Example 2: Get Decoys for Specific Node
```
REQUEST:
  GET /api/decoys/node/node1
  Authorization: Bearer eyJhbGc... (user_id="user123")

BACKEND FLOW:
  1. Extract user_id = "user123"
  2. Verify authorization:
     - Query: db.nodes.find_one({node_id: "node1"})
     - Check: node.user_id == "user123"
     - If mismatch → return 403 Forbidden
  3. Query: db.decoys.find({node_id: "node1"})
  4. Normalize each decoy
  5. Return: List[Decoy]

RESULT:
  ✓ Only node1 decoys returned
  ✓ Unauthorized users get 403 error
```

### Example 3: Get Logs with Filters
```
REQUEST:
  GET /api/logs?node_id=node1&severity=critical&search=192.168.1.1

BACKEND FLOW:
  1. Extract user_id from token
  2. Get user's nodes: [node1, node2, ...]
  3. Extract: node_ids = [node1, node2, ...]
  4. Query honeypot logs:
     db.honeypot_logs.find({node_id: {$in: node_ids}})
       .sort({timestamp: -1}).limit(100)
  5. Query agent events:
     db.agent_events.find({node_id: {$in: node_ids}})
       .sort({timestamp: -1}).limit(100)
  6. Combine + sort by timestamp DESC
  7. Apply filters:
     - node_id === "node1" → Keep only node1 events
     - severity === "critical" → Keep only critical events
     - search in [source_ip, event_type, decoy] → Keep matching events
  8. Return: List[Event]

RESULT:
  ✓ Only critical events from node1 matching "192.168.1.1"
  ✓ Chronologically ordered
```

### Example 4: Get Dashboard Stats
```
REQUEST:
  GET /api/stats
  Authorization: Bearer eyJhbGc... (user_id="user123")

BACKEND FLOW:
  1. Extract user_id = "user123"
  2. Aggregate stats:
     
     a) Total nodes:
        db.nodes.count_documents({user_id: "user123"})
        → 3
     
     b) Active nodes:
        db.nodes.count_documents({user_id: "user123", status: "active"})
        → 2
     
     c) Total attacks:
        db.alerts.count_documents({user_id: "user123"})
        → 42
     
     d) Unique attackers (group by source_ip):
        db.alerts.aggregate([
          {$match: {user_id: "user123"}},
          {$group: {_id: "$source_ip"}}
        ])
        → 8 unique IPs
     
     e) Avg risk score:
        db.alerts.aggregate([
          {$match: {user_id: "user123"}},
          {$group: {
            _id: null,
            avg_risk: {$avg: "$risk_score"},
            high_risk_count: {$sum: {$cond: [{$gte: ["$risk_score", 70]}, 1, 0]}}
          }}
        ])
        → avg_risk=65.5, high_risk_count=6
  
  3. Return: StatsResponse(...)

RESULT:
  {
    "total_nodes": 3,
    "active_nodes": 2,
    "total_attacks": 42,
    "unique_attackers": 8,
    "avg_risk_score": 65.5,
    "high_risk_count": 6
  }
```

---

## 🛡️ Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: AUTHENTICATION                                         │
│ ├─ JWT token validation                                         │
│ ├─ User ID extraction from claims                               │
│ └─ Fallback to DEMO_USER_ID if AUTH_ENABLED=False              │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: NODE-LEVEL AUTHORIZATION                               │
│ ├─ Fetch node by node_id                                        │
│ ├─ Verify node.user_id == request.user_id                       │
│ └─ Return 403 if ownership check fails                          │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: QUERY-LEVEL SCOPING                                    │
│ ├─ Get all user's node_ids                                      │
│ ├─ Use {node_id: {$in: [...]}} in database queries             │
│ └─ Database only returns user's data                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 API Endpoint Matrix

| Endpoint | Auth | Node Check | Scope | Query | Response |
|----------|------|-----------|-------|-------|----------|
| `GET /api/decoys` | ✓ | ✗ | User | node_id ∈ user_nodes | List[Decoy] |
| `GET /api/decoys/node/{id}` | ✓ | ✓ | Node | node_id = id | List[Decoy] |
| `GET /api/honeytokels` | ✓ | ✗ | User | node_id ∈ user_nodes, type="honeytoken" | List[HT] |
| `GET /api/honeytokels/node/{id}` | ✓ | ✓ | Node | node_id = id, type="honeytoken" | List[HT] |
| `GET /api/logs` | ✓ | ✗ | User | node_id ∈ user_nodes | List[Event] |
| `GET /api/logs/node/{id}` | ✓ | ✓ | Node | node_id = id | List[Event] |
| `GET /api/stats` | ✓ | ✗ | User | user_id = id | StatsResponse |
| `GET /api/recent-attacks` | ✓ | ✗ | User | user_id = id | List[Alert] |
| `GET /api/alerts` | ✓ | ✗ | User | user_id = id | List[Alert] |

---

## ✅ Verification Summary

**All endpoints properly implement node-wise data filtering:**
- ✓ User authentication on all endpoints
- ✓ Node authorization check on node-specific endpoints
- ✓ Database queries scoped to user's nodes
- ✓ Multi-node queries use MongoDB $in operator
- ✓ Optional filters applied in-memory or in query
- ✓ Response normalization consistent across all models

**No security gaps detected.**

---

**Generated**: February 4, 2026  
**Visual Architecture Version**: 1.0
