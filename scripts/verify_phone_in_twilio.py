import urllib.request
import urllib.parse
import json
import base64
import sys
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

phone = sys.argv[1] if len(sys.argv) > 1 else "+919008474173"
friendly = sys.argv[2] if len(sys.argv) > 2 else "Deemanth Second Phone"

print(f"Initiating Twilio Caller ID verification for {phone}...")
payload = urllib.parse.urlencode({
    "PhoneNumber": phone,
    "FriendlyName": friendly
}).encode()

req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/OutgoingCallerIds.json",
    data=payload,
    headers=headers
)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        val_code = data.get("validation_code")
        print("\n============================================================")
        print(f"[SUCCESS] Twilio is now calling {phone}!")
        print(f"When you answer the phone, enter this 6-digit code on the keypad:")
        print(f"   >>> {val_code} <<<")
        print("============================================================\n")
except urllib.error.HTTPError as e:
    err_body = e.read().decode()
    print(f"HTTP Error {e.code}: {err_body}")
except Exception as e:
    print(f"Error: {e}")
