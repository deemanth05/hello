import urllib.request
import urllib.parse
import json
import base64
import sys

import os
from pathlib import Path

# Load from environment or sys.argv
account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")

# Fallback: parse from .env if present
if not account_sid or not auth_token:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("TWILIO_ACCOUNT_SID="):
                account_sid = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("TWILIO_AUTH_TOKEN="):
                auth_token = line.split("=", 1)[1].strip().strip('"').strip("'")

if len(sys.argv) > 1:
    webhook_url = sys.argv[1]
else:
    webhook_url = os.getenv("TWILIO_WEBHOOK_URL", "")

if not account_sid or not auth_token or not webhook_url:
    print("Usage: python scripts/setup_twilio_webhook.py <https://your-render-app.onrender.com/voice/incoming>")
    print("Ensure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are set in .env or environment.")
    sys.exit(1)

auth_str = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth_str}"
}

print("Querying Twilio Account for Incoming Phone Numbers...")
req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json",
    headers=headers
)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        numbers = data.get("incoming_phone_numbers", [])
        print(f"Found {len(numbers)} phone numbers on account:")
        
        for num in numbers:
            pn_sid = num["sid"]
            phone = num["phone_number"]
            old_url = num.get("voice_url")
            print(f" - Phone: {phone} (SID: {pn_sid})")
            print(f"   Current Voice URL: {old_url}")
            
            # Update Voice URL
            update_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers/{pn_sid}.json"
            payload = urllib.parse.urlencode({
                "VoiceUrl": webhook_url,
                "VoiceMethod": "POST"
            }).encode()
            
            update_req = urllib.request.Request(update_url, data=payload, headers=headers)
            with urllib.request.urlopen(update_req) as up_resp:
                up_data = json.loads(up_resp.read().decode())
                print(f"   -> SUCCESS! Updated Voice URL to: {up_data.get('voice_url')}")
                print(f"   -> Voice Method: {up_data.get('voice_method')}")
                
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
