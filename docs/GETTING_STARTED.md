# Getting Started: Clone, Setup & Run Guide

This guide provides step-by-step instructions for anyone cloning this repository to get the DMart Express Voice-AI system running locally or in the cloud in under 5 minutes.

---

## 1. Prerequisites

Before starting, ensure you have:
- **Git**: Installed on your system ([git-scm.com](https://git-scm.com/)).
- **Python 3.10, 3.11, or 3.12**: Verified via `python --version` ([python.org](https://www.python.org/)).
- **Choose Your Execution Mode**:
  - **Mode A: Cloud-Native Mode (Recommended - Fastest & Lightweight)**:
    - Zero local weights or models needed (~90 MB RAM).
    - Requires a free **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/).
  - **Mode B: 100% Local Inference Mode (Offline & Zero API Cost)**:
    - Requires [Ollama](https://ollama.com/) installed with `ollama run gemma3:latest` (or `qwen2.5:7b`).
    - Requires ~4 GB to 8 GB free RAM for Whisper and Piper TTS.

---

## 2. Step-by-Step Installation

### Step 1: Clone the Repository
Open your terminal or PowerShell and clone the codebase:
```bash
git clone https://github.com/deemanth05/hello.git
cd hello
```

### Step 2: Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**On Linux or macOS (Bash / Zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### Step 3: Install Dependencies

Choose depending on your intended setup:

#### Option 1: Cloud-Native Mode (Recommended)
Installs FastAPI, Uvicorn, Twilio SDK, and Google GenAI SDK (no PyTorch, Whisper, or local weights):
```bash
pip install -r requirements.txt
```

#### Option 2: Full Local AI Mode
Installs local Speech-to-Text (`faster-whisper`), Text-to-Speech (`piper-tts`), and audio hardware utilities (`sounddevice`):
```bash
pip install -r requirements-local.txt
```

---

### Step 4: Configure Environment Variables

Create your local `.env` file by copying `.env.example`:

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**On Linux / macOS:**
```bash
cp .env.example .env
```

Open `.env` in any text editor and configure:

```env
# Store Configuration
STORE_NAME="D mart Express"
STORE_PHONE="+17744930623"
LANGUAGE="kn"
PORT=8765

# If using Cloud Mode (Recommended):
GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"

# If using Twilio for real telephone calls:
TWILIO_ACCOUNT_SID="ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
TWILIO_AUTH_TOKEN="your_auth_token_here"
TWILIO_PHONE_NUMBER="+17744930623"

# If using Local AI Mode:
OLLAMA_HOST="http://localhost:11434"
OLLAMA_MODEL="gemma3:latest"
```

> [!NOTE]
> The SQLite database (`dmart_store.db`) is already included and pre-seeded with 22 grocery catalog items and registered customer profiles. If deleted, it automatically recreates and seeds itself on startup.

---

## 3. Verify Installation

Run the automated test suites to confirm database access, routing, and conversation logic:

```bash
# 1. Verify Database and Catalog Functions
python tests/test_db.py

# 2. Verify FastAPI Routes and Audio Codecs
python tests/test_server.py

# 3. Verify Kannada Multi-turn Flow
python tests/test_kannada_flow.py
```

All tests should report `PASSED` or exit code 0.

---

## 4. Run the System

You can run and interact with the system in four different ways:

### Way 1: Web Dashboard & In-Browser Simulator (Fastest)

Start the server:
```bash
python -m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8765
```

Open your browser at:
👉 **`http://localhost:8765`**

From the dashboard you can:
- View live store operational status and registered customer count.
- Inspect the recent grocery orders feed with item-by-item breakdown.
- Use the **Browser Call Simulator** to type Kannada/English messages and see the AI agent's responses, tool executions, and orders placed in real-time.

---

### Way 2: Terminal Interactive Caller Simulator

Test conversational ordering directly from your terminal:
```bash
python run_simulator.py
```

1. Select caller identity:
   - `[1] Registered Customer (Rahul Sharma, +919876543210)`
   - `[2] Registered Customer (Priya Patel, +919812345678)`
   - `[3] Unregistered New Caller`
2. Choose mode:
   - `[1] Text Chat Mode`: Type in Kannada (*"ನನಗೆ ಹಾಲು ಮತ್ತು ಸಕ್ಕರೆ ಬೇಕು"*) or English (*"I need 2 packets of milk"*).
   - `[2] Live Microphone Mode`: Speak aloud into your computer microphone.

---

### Way 3: Real Inbound Phone Calls (Twilio + Cloudflare Tunnel)

To receive real phone calls on a Twilio telephone number:

1. **Start the Telephony Server**:
   ```powershell
   python -m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8765
   ```

2. **Expose your server to the Internet**:
   Using the bundled Cloudflare Tunnel binary:
   ```powershell
   .\cloudflared.exe tunnel --url http://localhost:8765
   ```
   *(Or using ngrok: `ngrok http 8765`)*.
   Note down the public HTTPS domain (e.g. `https://rapid-fox-tunnel.trycloudflare.com`).

3. **Configure the Twilio Webhook**:
   Run the automated configuration script:
   ```powershell
   python scripts/setup_twilio_webhook.py https://<your-tunnel-url>/voice/incoming
   ```

4. **Make a Call**:
   Dial your Twilio store phone number from your mobile phone. The bot will answer in Kannada!

---

### Way 4: Free Cloud Deployment on Render

To deploy permanently online so you don't need to keep your laptop running:

1. Push your repository to GitHub.
2. Sign up on [Render.com](https://render.com/).
3. Click **New +** $\to$ **Web Service** $\to$ Connect your GitHub repo.
4. Render automatically reads [`render.yaml`](file:///c:/Users/deema/Desktop/hello/render.yaml) and [`Procfile`](file:///c:/Users/deema/Desktop/hello/Procfile).
5. In the **Environment Variables** tab, add:
   - `GEMINI_API_KEY`: Your Google Gemini API key.
6. Click **Deploy Web Service**.
7. Once live, point your Twilio phone number's Voice Webhook to:
   ```
   https://<your-render-subdomain>.onrender.com/voice/incoming (HTTP POST)
   ```

---

## 5. Troubleshooting & FAQ

### Port 8765 already in use
If another process is using port 8765:
```powershell
# Windows
Get-Process -Id (Get-NetTCPConnection -LocalPort 8765).OwningProcess | Stop-Process -Force

# Linux / macOS
lsof -ti:8765 | xargs kill -9
```
Or start on a different port:
```bash
python -m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8080
```

### Twilio Free Trial: "An application error has occurred" or Busy Tone
- On Twilio Free Trial accounts, inbound calls **must** originate from a **Verified Caller ID**.
- Register your personal mobile number in Twilio Console: **Phone Numbers $\to$ Manage $\to$ Verified Caller IDs**, or run:
  ```powershell
  python scripts/verify_phone_in_twilio.py +91XXXXXXXXXX
  ```

### Cloud Mode vs Local Mode Memory Usage
- **Cloud Mode (`GEMINI_API_KEY` set)**: Consumes ~90 MB RAM. Perfect for free tier cloud instances (Render, Railway, Fly.io).
- **Local Mode (No API key)**: Loads Faster-Whisper and Piper TTS neural models locally, requiring ~4 GB RAM. Ensure Ollama is running (`ollama serve`).

---

## 6. Project Architecture & Docs Reference

For deeper technical specifications, see:
- **[System Architecture](ARCHITECTURE.md)**: Transcoding pipelines & sequence diagrams.
- **[API Reference](API_REFERENCE.md)**: Webhook schemas & WebSocket protocol.
- **[Database Schema](DATABASE.md)**: SQLite tables, customer profiles & catalog items.
- **[Tools Reference](TOOLS_REFERENCE.md)**: Deterministic function execution details.
- **[Telephony Setup](TELEPHONY_SETUP.md)**: Comprehensive Twilio configuration guide.
