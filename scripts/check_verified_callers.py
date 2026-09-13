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

req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/OutgoingCallerIds.json",
    headers=headers
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    callers = data.get("outgoing_caller_ids", [])
    print(f"Total verified caller IDs on Twilio: {len(callers)}")
    for c in callers:
        print(f" - Phone: {c.get('phone_number')} (Friendly: {c.get('friendly_name')})")
