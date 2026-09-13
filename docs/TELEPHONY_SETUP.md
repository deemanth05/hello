# Telephony Integration & Deployment Guide (Twilio, Render & Cloudflare)

This guide walks you through connecting your DMart Voice-AI server to a live telephone number via **Twilio Voice Webhooks and Bi-directional Media Streams**.

---

## 1. Prerequisites

1. An active [Twilio Account](https://www.twilio.com/) (Trial or Paid).
2. A purchased Twilio phone number (e.g. `+17744930623`).
3. Either:
   - **Cloud Hosting on Render** (`https://<app>.onrender.com`), OR
   - **Local Tunnel**: Cloudflare Tunnel (`cloudflared.exe` included) or ngrok.

---

## 2. Telephony Hosting Options

### Option A: 24/7 Cloud Hosting on Render (Recommended)
With Render cloud deployment, the server runs permanently on the web with native SSL (`https://` and `wss://`). No laptop, ngrok, or Cloudflare tunnel is required:
- Public Voice Webhook: `https://<your-service>.onrender.com/voice/incoming`
- WebSocket Stream: `wss://<your-service>.onrender.com/voice/stream`

### Option B: Local Cloudflare Tunnel (`cloudflared.exe`)
For local laptop testing:
```powershell
.\cloudflared.exe tunnel --url http://localhost:8765
```
Cloudflare outputs a public domain (e.g. `https://random-words.trycloudflare.com`).

---

## 3. Configuring Twilio Voice Webhook

### Method 1: Automated Configuration Script (Fastest)
The repository provides `scripts/setup_twilio_webhook.py` to configure your Twilio phone number programmatically via the Twilio REST API:

```powershell
.venv\Scripts\python.exe scripts/setup_twilio_webhook.py https://<YOUR_DOMAIN>/voice/incoming
```

The script will automatically discover all active phone numbers on your Twilio account and update each number's `VoiceUrl` to `https://<YOUR_DOMAIN>/voice/incoming` (HTTP POST).

### Method 2: Manual Twilio Console Configuration
1. Log in to the [Twilio Console](https://console.twilio.com/).
2. Navigate to **Phone Numbers** $\to$ **Manage** $\to$ **Active Numbers**.
3. Click on your active phone number.
4. Scroll down to **Voice Configuration**:
   - **A CALL COMES IN**: Select **Webhook**.
   - **URL**: Paste `https://<YOUR_DOMAIN>/voice/incoming`.
   - **HTTP METHOD**: Select `HTTP POST`.
5. Click **Save Configuration**.

---

## 4. ⚠️ Critical Twilio Free Trial Requirements

If your Twilio account is in **Free Trial Mode**, Twilio strictly enforces the following:

### 1. Verified Caller ID Requirement
Twilio blocks inbound calls from any number that has not been explicitly verified:
- **How to Verify**: Go to [**Twilio Verified Caller IDs**](https://console.twilio.com/us1/develop/phone-numbers/manage/verified-caller-ids) and verify your mobile number via SMS OTP.
- **Automated Verification Call Script**:
  ```powershell
  .venv\Scripts\python.exe scripts/verify_phone_in_twilio.py +91XXXXXXXXXX
  ```
  Twilio will place a verification call to the handset; type the displayed 6-digit code on the phone dialpad.

### 2. International Dialing Format
The Twilio phone number is a US number (`+1...`).
- When dialing from India, always include the `+` sign (long-press `0` on mobile dialpad).
- Ensure your mobile SIM card has international outgoing (ISD) talktime or pack active.

---

## 5. Telephony Management Scripts Suite (`scripts/`)

| Script | Purpose |
| :--- | :--- |
| `scripts/setup_twilio_webhook.py <URL>` | Updates Twilio phone number webhook to the given URL |
| `scripts/add_customer.py <PHONE> <NAME> <ADDR>` | Registers new test customer in SQLite (`--list` to view) |
| `scripts/check_numbers.py` | Queries Twilio REST API for active numbers & current voice URLs |
| `scripts/check_verified_callers.py` | Lists all phone numbers verified to place calls to trial numbers |
| `scripts/verify_phone_in_twilio.py <PHONE>` | Triggers outbound Twilio phone call to verify a new caller ID |
| `scripts/check_twilio_logs.py` | Fetches recent incoming call records and statuses from Twilio |

---

## 6. How the Phone Call Operates

1. **Incoming Ring**: You dial your Twilio phone number from any verified handset.
2. **Webhook Request**: Twilio sends an HTTP POST to `/voice/incoming`.
3. **TwiML Handshake**: The server looks up the caller in SQLite and returns standard TwiML:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
       <Connect>
           <Stream url="wss://<YOUR_DOMAIN>/voice/stream">
               <Parameter name="caller" value="+919876543210" />
           </Stream>
       </Connect>
   </Response>
   ```
4. **WebSocket Media Stream**: Twilio opens a bi-directional WebSocket connection to `/voice/stream`.
5. **Conversational Turn**:
   - The AI welcomes the caller in Kannada by name.
   - Caller audio is streamed in 20ms G.711 $\mu$-law frames.
   - The AI resolves items, searches the catalog, checks stock, and commits orders with dynamic ETAs.
   - Audio is streamed back seamlessly to the caller's phone speaker.
