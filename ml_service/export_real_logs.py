"""
Export Real Logs from MongoDB and Convert to ML Training Dataset
Connects to production MongoDB and extracts features from actual honeypot/agent logs
"""

import os
import sys
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
from feature_extractor import FeatureExtractor

# MongoDB connection
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://decoyverse_user:XF07W87YU4JWVY8f@decoy.ygwnyen.mongodb.net/decoyvers?retryWrites=true&w=majority"
)
DATABASE_NAME = "decoyvers"
HONEYPOT_LOGS_COLLECTION = "honeypot_logs"
AGENT_EVENTS_COLLECTION = "agent_events"

OUTPUT_FILE = "real_logs_dataset.csv"


def connect_to_mongodb():
    """Connect to MongoDB Atlas"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print(f"✓ Connected to MongoDB: {DATABASE_NAME}")
        return client[DATABASE_NAME]
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        sys.exit(1)


def convert_honeypot_log_to_features(log: Dict[str, Any]) -> Dict[str, float]:
    """
    Convert honeypot log to ML features
    
    Maps raw log data to feature schema:
    - failed_logins: Count from payload/activity
    - request_rate: Estimate from service type
    - commands_count: Parse from payload
    - sql_payload: Detect SQL injection patterns
    - honeytoken_access: Always 0 for honeypot logs
    - session_time: Estimate from timestamp
    """
    features = {
        'failed_logins': 0,
        'request_rate': 0,
        'commands_count': 0,
        'sql_payload': 0,
        'honeytoken_access': 0,
        'session_time': 0
    }
    
    activity = log.get('activity', '').lower()
    payload = log.get('payload', '').lower()
    service = log.get('service', '').upper()
    
    # Failed logins detection
    if 'login' in activity or 'auth' in activity:
        if 'failed' in activity or 'attempt' in activity:
            features['failed_logins'] = log.get('extra', {}).get('attempts', 1)
    
    # Request rate (estimate based on service)
    if service == 'WEB':
        features['request_rate'] = 100  # Web services have higher request rates
    elif service == 'SSH':
        features['request_rate'] = 10
    elif service == 'FTP':
        features['request_rate'] = 20
    
    # Commands count (parse from payload)
    command_keywords = ['wget', 'curl', 'nc', 'bash', 'sh', 'python', 'perl', 'exec']
    features['commands_count'] = sum(1 for cmd in command_keywords if cmd in payload)
    
    # SQL injection detection
    sql_patterns = ['select', 'union', 'drop', 'insert', 'update', 'delete', '--', 'or 1=1', 'admin\'--']
    if any(pattern in payload for pattern in sql_patterns):
        features['sql_payload'] = 1
    
    # Session time (default 60s for honeypot interactions)
    features['session_time'] = 60
    
    return features


def convert_agent_event_to_features(event: Dict[str, Any]) -> Dict[str, float]:
    """
    Convert agent honeytoken event to ML features
    
    Agent events indicate honeytoken access - always high risk
    """
    features = {
        'failed_logins': 0,
        'request_rate': 0,
        'commands_count': 0,
        'sql_payload': 0,
        'honeytoken_access': 1,  # Always 1 for agent events
        'session_time': 0
    }
    
    # Honeytoken access is critical
    action = event.get('action', '').upper()
    severity = event.get('severity', '').upper()
    
    # Adjust based on severity
    if severity == 'CRITICAL':
        features['session_time'] = 300  # Longer session = more suspicious
    elif severity == 'HIGH':
        features['session_time'] = 180
    else:
        features['session_time'] = 60
    
    # If modified, increase risk indicators
    if action == 'MODIFIED':
        features['commands_count'] = 5
    
    return features


def auto_label_log(features: Dict[str, float]) -> str:
    """
    Auto-label logs using rule-based logic
    
    Priority order (highest to lowest):
    1. Honeytoken access → DataExfil
    2. Failed logins > 50 → BruteForce
    3. SQL payload detected → Injection
    4. Request rate > 300 → Recon
    5. Default → Normal
    """
    if features['honeytoken_access'] == 1:
        return 'DataExfil'
    elif features['failed_logins'] > 50:
        return 'BruteForce'
    elif features['sql_payload'] == 1:
        return 'Injection'
    elif features['request_rate'] > 300:
        return 'Recon'
    else:
        return 'Normal'


def export_logs_to_dataset():
    """Main export function"""
    print("=" * 60)
    print("DECOYVERS ML TRAINING DATA EXPORT")
    print("=" * 60)
    
    # Connect to MongoDB
    db = connect_to_mongodb()
    
    # Fetch logs
    print(f"\n📥 Fetching logs from MongoDB...")
    honeypot_logs = list(db[HONEYPOT_LOGS_COLLECTION].find({}))
    agent_events = list(db[AGENT_EVENTS_COLLECTION].find({}))
    
    print(f"  - Honeypot logs: {len(honeypot_logs)}")
    print(f"  - Agent events: {len(agent_events)}")
    
    if len(honeypot_logs) == 0 and len(agent_events) == 0:
        print("\n⚠️  No logs found in database. Generate some test data first.")
        sys.exit(1)
    
    # Convert to features
    print(f"\n🔄 Converting logs to ML features...")
    dataset = []
    
    # Process honeypot logs
    for log in honeypot_logs:
        features = convert_honeypot_log_to_features(log)
        features['label'] = auto_label_log(features)
        features['source'] = 'honeypot'
        features['timestamp'] = log.get('timestamp', '')
        dataset.append(features)
    
    # Process agent events
    for event in agent_events:
        features = convert_agent_event_to_features(event)
        features['label'] = auto_label_log(features)
        features['source'] = 'agent'
        features['timestamp'] = event.get('timestamp', '')
        dataset.append(features)
    
    # Create DataFrame
    df = pd.DataFrame(dataset)
    
    # Show label distribution
    print(f"\n📊 Label distribution:")
    print(df['label'].value_counts().to_string())
    
    # Save to CSV
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✓ Dataset saved to: {OUTPUT_FILE}")
    print(f"  Total samples: {len(df)}")
    print(f"  Features: {FeatureExtractor.FEATURE_ORDER}")
    print(f"  Labels: {df['label'].unique().tolist()}")
    
    return df


if __name__ == '__main__':
    export_logs_to_dataset()
