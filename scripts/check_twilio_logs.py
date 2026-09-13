import urllib.request
import json
import base64
import os
from pathlib import Path

# Load credentials from .env
env_path = Path(__file__).resolve().parent.parent / ".env"
account_sid = ""
auth_token = ""
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("TWILIO_ACCOUNT_SID="):
            account_sid = line.split("=", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("TWILIO_AUTH_TOKEN="):
            auth_token = line.split("=", 1)[1].strip().strip('"').strip("'")

auth_str = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
headers = {"Authorization": f"Basic {auth_str}"}

print("=== RECENT TWILIO CALLS ===")
req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json?PageSize=20",
    headers=headers
)
try:
    with urllib.request.urlopen(req) as resp:
        calls = json.loads(resp.read().decode()).get("calls", [])
        for c in calls:
            print(f"Call: {c['sid']} | From: {c['from']} | To: {c['to']} | Status: {c['status']} | Duration: {c['duration']}s | Start: {c['start_time']}")
except Exception as e:
    print(f"Error fetching calls: {e}")

print("\n=== TWILIO DEBUGGER ALERTS / NOTIFICATIONS ===")
n_req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Notifications.json?PageSize=5",
    headers=headers
)
try:
    with urllib.request.urlopen(n_req) as resp:
        notifs = json.loads(resp.read().decode()).get("notifications", [])
        if not notifs:
            print("No recent debugger notifications found.")
        for n in notifs:
            print(f"Notification: Error {n.get('error_code')} - {n.get('message_text')} | Call SID: {n.get('call_sid')} | Date: {n.get('message_date')}")
except Exception as e:
    print(f"Error fetching notifications: {e}")
