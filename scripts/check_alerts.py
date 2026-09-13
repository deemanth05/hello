import urllib.request
import json
import base64
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
account_sid = ""
auth_token = ""
for line in env_path.read_text().splitlines():
    if line.startswith("TWILIO_ACCOUNT_SID="):
        account_sid = line.split("=", 1)[1].strip().strip('"').strip("'")
    elif line.startswith("TWILIO_AUTH_TOKEN="):
        auth_token = line.split("=", 1)[1].strip().strip('"').strip("'")

auth_str = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
headers = {"Authorization": f"Basic {auth_str}"}

print("=== CHECKING TWILIO DEBUGGER / MONITOR ALERTS ===")
req = urllib.request.Request(
    "https://monitor.twilio.com/v1/Alerts?PageSize=5",
    headers=headers
)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        alerts = data.get("alerts", [])
        print(f"Found {len(alerts)} alerts:")
        for a in alerts:
            print(f"Error Code:   {a.get('error_code')}")
            print(f"Alert Text:   {a.get('alert_text')}")
            print(f"Date:         {a.get('date_created')}")
            print(f"Request URL:  {a.get('request_url')}")
            print(f"Resource SID: {a.get('resource_sid')}")
            print("-" * 50)
except Exception as e:
    print("Error:", e)
