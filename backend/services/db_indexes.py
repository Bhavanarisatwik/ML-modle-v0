"""
Database Index Initialization
Creates MongoDB indexes for performance and uniqueness
"""

from config import (
    USERS_COLLECTION,
    NODES_COLLECTION,
    ALERTS_COLLECTION,
    DECOYS_COLLECTION,
    HONEYPOT_LOGS_COLLECTION,
    AGENT_EVENTS_COLLECTION
)


async def create_indexes(db):
    """Create MongoDB indexes for performance and uniqueness"""
    # Users
    await db[USERS_COLLECTION].create_index("email", unique=True)

    # Nodes
    await db[NODES_COLLECTION].create_index("node_id", unique=True)
    await db[NODES_COLLECTION].create_index("user_id")

    # Alerts
    await db[ALERTS_COLLECTION].create_index("user_id")
    await db[ALERTS_COLLECTION].create_index("risk_score")
    await db[ALERTS_COLLECTION].create_index("timestamp")

    # Decoys
    await db[DECOYS_COLLECTION].create_index("node_id")

    # Honeypot logs
    await db[HONEYPOT_LOGS_COLLECTION].create_index("node_id")
    await db[HONEYPOT_LOGS_COLLECTION].create_index("timestamp")

    # Agent events
    await db[AGENT_EVENTS_COLLECTION].create_index("node_id")
    await db[AGENT_EVENTS_COLLECTION].create_index("timestamp")
