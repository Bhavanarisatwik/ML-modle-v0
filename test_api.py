import requests

# API endpoint
url = "http://localhost:8000/predict"

# Test case: Brute Force Attack
log = {
    "failed_logins": 120,
    "request_rate": 200,
    "commands_count": 0,
    "sql_payload": 0,
    "honeytoken_access": 0,
    "session_time": 600
}

response = requests.post(url, json=log)
print("Status Code:", response.status_code)
print("Response:", response.json())