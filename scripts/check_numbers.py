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
    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json",
    headers=headers
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    numbers = data.get("incoming_phone_numbers", [])
    print(f"Total numbers on account: {len(numbers)}")
    for n in numbers:
        print("Phone Number:", n.get("phone_number"))
        print("SID:         ", n.get("sid"))
        print("Voice URL:   ", n.get("voice_url"))
        print("Voice Method:", n.get("voice_method"))
        print("Capabilities:", n.get("capabilities"))
        print("Status:      ", n.get("status"))
