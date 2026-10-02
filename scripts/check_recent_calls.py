import urllib.request
import json
import base64
from pathlib import Path

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
    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json?PageSize=10",
    headers=headers
)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        calls = data.get("calls", [])
        print(f"Total calls: {len(calls)}")
        for c in calls:
            print(f"SID: {c['sid']} | Status: {c.get('status')} | Duration: {c.get('duration')}s | Start: {c.get('start_time')} | End: {c.get('end_time')}")
            
            # Fetch notifications / debug logs for this call SID
            notif_req = urllib.request.Request(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{c['sid']}/Notifications.json",
                headers=headers
            )
            try:
                with urllib.request.urlopen(notif_req) as n_resp:
                    n_data = json.loads(n_resp.read().decode())
                    for n in n_data.get("notifications", []):
                        print(f"   -> Alert [{n.get('error_code')}]: {n.get('message_text')} (HTTP {n.get('http_response_code')})")
            except Exception as ne:
                pass
except Exception as e:
    print(f"Error: {e}")
