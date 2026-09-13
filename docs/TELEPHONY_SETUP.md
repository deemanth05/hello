# Telephony Integration & Deployment Guide (Twilio & Cloudflare/ngrok)

This guide walks you through connecting your local or cloud DMart Voice-AI server to a live telephone number via **Twilio Voice Webhooks and Bi-directional Media Streams**.

---

## 1. Prerequisites

1. An active [Twilio Account](https://www.twilio.com/).
2. A purchased Twilio phone number (US or International).
3. A public HTTPS/WSS tunnel:
   - **Cloudflare Tunnel** (`cloudflared.exe` included in this repository), OR
   - **ngrok** (`ngrok http 8765`).

---

## 2. Exposing the Local Server to the Public Internet

Twilio requires a public HTTPS/WSS endpoint to route call media streams.

### Option A: Using the Bundled Cloudflare Tunnel (Free, No Signup Required)

The workspace includes `cloudflared.exe`. Run the following command in PowerShell:

```powershell
.\cloudflared.exe tunnel --url http://localhost:8765
```

Cloudflare will generate a public URL such as:
```
https://random-words-123.trycloudflare.com
```

### Option B: Using ngrok

If you have ngrok installed:

```powershell
ngrok http 8765
```

Note the forwarded HTTPS domain (e.g., `https://abc123.ngrok-free.app`).

---

## 3. Configuring Twilio Voice Webhook

### Method 1: Automated Configuration Script
The project provides `scripts/setup_twilio_webhook.py` to configure your Twilio phone number programmatically via the Twilio REST API.

1. Ensure your `.env` contains:
```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
```

2. Run the update script:
```powershell
.venv\Scripts\python.exe scripts/setup_twilio_webhook.py https://random-words-123.trycloudflare.com/voice/incoming
```

The script will:
- Discover all numbers on your Twilio account.
- Update each number's `VoiceUrl` to `https://<DOMAIN>/voice/incoming` with HTTP `POST`.

---

### Method 2: Manual Twilio Console Configuration

1. Log in to the [Twilio Console](https://console.twilio.com/).
2. Navigate to **Phone Numbers** $\to$ **Manage** $\to$ **Active Numbers**.
3. Click on your phone number.
4. Scroll down to the **Voice Configuration** section:
   - **A CALL COMES IN**: Select **Webhook**.
   - **URL**: Paste `https://<YOUR_TUNNEL_DOMAIN>/voice/incoming`.
   - **HTTP METHOD**: Select `HTTP POST`.
5. Click **Save Configuration**.

---

## 4. How the Phone Call Operates

1. **Incoming Ring**: You dial your Twilio phone number from any mobile or landline handset.
2. **Webhook Request**: Twilio sends an HTTP POST request to `https://<YOUR_TUNNEL_DOMAIN>/voice/incoming`.
3. **TwiML Handshake**: The server looks up your phone number in SQLite and replies with TwiML `<Connect><Stream url="wss://<DOMAIN>/voice/stream">`.
4. **WebSocket Media Stream**: Twilio opens a bi-directional WebSocket connection to `/voice/stream`.
5. **Conversational Turn**:
   - The AI welcomes you in Kannada.
   - When you speak, audio is transcoded from 8kHz $\mu$-law to 16kHz linear PCM.
   - Faster-Whisper transcribes your voice.
   - Gemma 3 / Qwen 2.5 executes grocery tools (catalog search, stock check, order placement).
   - Piper TTS generates natural Kannada speech.
   - Audio is transcoded to 8kHz $\mu$-law and streamed back to your handset with zero stutter.
