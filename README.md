# DMart Express - Voice-AI Telephony System (ಕನ್ನಡ & English)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0+-009688.svg)](https://fastapi.tiangolo.com/)
[![Gemini 2.5 Live](https://img.shields.io/badge/Gemini_2.5_Live-Speech--to--Speech-4285F4.svg)](https://ai.google.dev/)
[![Ollama](https://img.shields.io/badge/Ollama-gemma3%20%7C%20qwen2.5-black.svg)](https://ollama.com/)
[![Twilio](https://img.shields.io/badge/Twilio-Media%20Streams-F22F46.svg)](https://www.twilio.com/)
[![Render](https://img.shields.io/badge/Render-Cloud%20Deployment-46E3B7.svg)](https://render.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade, bilingual (**Kannada / ಕನ್ನಡ & English**) automated telephone ordering system for supermarkets and grocery stores. Features **Cloud-Native Speech-to-Speech (Gemini 2.5 Live Multimodal)** for sub-500ms real-time calls with acoustic barge-in, a **100% Local Inference Mode** (Faster-Whisper + Ollama + Piper TTS) for zero API costs, deterministic caller identification, natural language grocery catalog search, dynamic delivery arrival times (ETA), a web management dashboard, and bi-directional Twilio telephony integration.

---

## 🌐 Live Cloud Deployment

The service is configured for zero-overhead deployment on **Render**:

- **Live URL**: `https://hello-8ct1.onrender.com`
- **Management Dashboard**: `https://hello-8ct1.onrender.com/` (Interactive Store Status, Live Orders Feed, and Web Call Simulator)
- **Twilio Voice Webhook**: `https://hello-8ct1.onrender.com/voice/incoming` (HTTP POST)
- **Twilio Store Phone**: `+1 (774) 493-0623`
- **Memory Footprint**: ~90 MB RAM on Render Free Tier via selective lazy-loading.

---

## 📚 Complete Documentation Index

| Document | Description |
| :--- | :--- |
| **[System Architecture](docs/ARCHITECTURE.md)** | Technical design, Dual-Mode lazy loading, audio transcoding pipelines (8kHz $\mu$-law $\leftrightarrow$ 16/24kHz PCM), and sequence diagrams |
| **[API Reference](docs/API_REFERENCE.md)** | Full specification of REST endpoints (`/`, `/health`, `/api/orders`, `/api/simulate/call`), Twilio webhook, and WebSocket streaming events |
| **[Database & Models](docs/DATABASE.md)** | SQLite WAL schema, table definitions, pre-seeded customer profiles, phone normalization, and semantic grocery synonyms |
| **[Voice AI Pipeline](docs/VOICE_PIPELINE.md)** | Gemini 2.5 Live Speech-to-Speech, Faster-Whisper STT, Ollama LLM integration, and Piper TTS phonetic transliteration |
| **[Tool Calling Reference](docs/TOOLS_REFERENCE.md)** | Deterministic function-calling specifications (`search_catalog`, `place_order`, `register_caller`, `check_stock`, etc.) |
| **[Telephony Setup Guide](docs/TELEPHONY_SETUP.md)** | Twilio setup, Render production deployment, Cloudflare Tunnel (`cloudflared.exe`), and developer utility scripts |
| **[Simulator & Testing Guide](docs/SIMULATOR_AND_TESTING.md)** | Interactive CLI simulator (Text & Mic modes), automated test suites, and WebSocket E2E testing |
| **[Deployment & Operations](docs/DEPLOYMENT_AND_OPERATIONS.md)** | Render Cloud specifications (`render.yaml`, `Procfile`), local service setup, and keep-alive pingers |

---

## 🌟 Key Features

1. **Bilingual Conversational AI (Kannada & English)**:
   - Understands native Kannada script, colloquial phrasing, and Kanglish (e.g. *"ನನಗೆ 2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಮತ್ತು ಒಂದು ಬ್ರೆಡ್ ಬೇಕು"*, *"ಚಹಾ ಪುಡಿ ಮತ್ತು ಸಕ್ಕರೆ"*).
   - Powered in the cloud by **Gemini 2.5 Flash Native Audio** with sub-500ms voice turnaround and direct acoustic interruption detection (barge-in).
   - Powered locally by **`gemma3:latest`** (or `qwen2.5:7b`) with universal function calling, **Faster-Whisper** (`base` / `small`), and **Piper TTS** with custom phonetic Kannada transliteration.

2. **Deterministic Caller Recognition**:
   - **Registered Customers**: Welcomed warmly by name in Kannada (*"ನಮಸ್ಕಾರ {name}, D mart Express ಗೆ ಸ್ವಾಗತ!"*). The AI **never asks** for phone number or address—it automatically pulls saved details from SQLite.
   - **Unregistered Callers**: Welcomed, prompted for their name and delivery address, atomically registered via `register_caller`, and transitioned seamlessly to order taking.

3. **Dynamic Delivery ETA & Order Commit**:
   - Computes delivery arrival windows dynamically based on current time (e.g. *"30 ರಿಂದ 40 ನಿಮಿಷಗಳಲ್ಲಿ, ಸುಮಾರು 9:45 PM ಗೆ ಬರುತ್ತದೆ"*).
   - Generates a full spoken summary in Kannada: items ordered, total amount in rupees (ರೂಪಾಯಿ), delivery address, and expected arrival time.
   - Atomic inventory deduction with rollback and cancellation stock restoration.

4. **Web Management Dashboard & Browser Simulator**:
   - Clean responsive interface at `/` displaying store statistics, live orders with item details, and an in-browser call simulator to test dialog flows.

---

## 🚀 Quick Start

### 1. Installation

#### Cloud / Lightweight Setup (Recommended for Cloud Hosting & Gemini Live)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

#### Local Edge Inference Stack (Whisper + Piper TTS)
If running fully offline with local neural models:
```powershell
pip install -r requirements-local.txt
```
Ensure [Ollama](https://ollama.com/) is installed and running:
```bash
ollama run gemma3:latest
```

### 2. Environment Configuration
Copy `.env.example` to `.env` and fill in credentials:
```env
STORE_NAME="D mart Express"
STORE_PHONE="+17744930623"
LANGUAGE="kn"
SERVER_PORT=8765

# For Cloud Mode (Gemini 2.5 Live Speech-to-Speech)
GEMINI_API_KEY="your-gemini-api-key"

# For Twilio Telephony Webhook Management
TWILIO_ACCOUNT_SID="your-account-sid"
TWILIO_AUTH_TOKEN="your-auth-token"
TWILIO_PHONE_NUMBER="+17744930623"
```

### 3. Run Automated Tests
```powershell
# Database and repository integrity
python tests/test_db.py

# Telephony server routes and audio transcoding
python tests/test_server.py

# Kannada conversation flow
python tests/test_kannada_flow.py
```

### 4. Interactive Testing
- **In-Browser Simulator**: Open `http://localhost:8765/` (or `https://hello-8ct1.onrender.com/`).
- **Terminal Simulator**:
  ```powershell
  python run_simulator.py
  ```
- **End-to-End WebSocket Stream Test**:
  ```powershell
  python test_e2e_call.py https://hello-8ct1.onrender.com +917676219923
  ```

---

## 📞 Telephony Deployment

### Option A: Live Render Cloud Deployment (Primary)
The system is pre-configured with `render.yaml` and `Procfile`.
1. Fork or push this repository to GitHub.
2. Link repository to [Render](https://render.com/) as a Web Service (Python 3 runtime).
3. Set environment variable: `GEMINI_API_KEY`.
4. Point Twilio Voice Webhook to `https://<your-render-app>.onrender.com/voice/incoming` (HTTP POST) or run:
   ```powershell
   python scripts/setup_twilio_webhook.py https://<your-render-app>.onrender.com/voice/incoming
   ```

### Option B: Local Telephony via Cloudflare Tunnel
1. **Start the Telephony Server**:
   ```powershell
   python -m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8765
   ```
2. **Launch Cloudflare Tunnel**:
   ```powershell
   .\cloudflared.exe tunnel --url http://localhost:8765
   ```
3. **Update Twilio**:
   ```powershell
   python scripts/setup_twilio_webhook.py https://<YOUR_CLOUDFLARE_DOMAIN>/voice/incoming
   ```

---

## 📁 Repository Structure

```
hello/
├── Procfile                       # Render deployment process definition
├── render.yaml                    # Infrastructure-as-Code Blueprint for Render
├── README.md                      # Master project overview & documentation hub
├── requirements.txt               # Production cloud dependencies (FastAPI, Google GenAI, Twilio)
├── requirements-local.txt         # Local AI dependencies (Faster-Whisper, Piper TTS, Ollama)
├── .env.example                   # Environment configuration template
├── dmart_store.db                 # SQLite database (customers, catalog, orders)
├── cloudflared.exe                # Bundled Cloudflare Tunnel binary
├── run_simulator.py               # Interactive CLI simulator (Text & Mic voice)
├── test_e2e_call.py               # End-to-end WebSocket client call simulation
│
├── docs/                          # Comprehensive Technical Documentation
│   ├── ARCHITECTURE.md            # System architecture, Dual-Mode lazy loading & audio transcoding
│   ├── API_REFERENCE.md           # REST endpoints, Twilio webhook & WebSocket protocol reference
│   ├── DATABASE.md                # Schema, models, pre-seeded customers & synonym mappings
│   ├── DEPLOYMENT_AND_OPERATIONS.md # Render Cloud, hardware sizing & operations guide
│   ├── SIMULATOR_AND_TESTING.md   # Testing guide, test suites & E2E caller simulator
│   ├── TELEPHONY_SETUP.md         # Twilio webhook, Free Trial verification & utility scripts
│   ├── TOOLS_REFERENCE.md         # Deterministic tool specifications & return structures
│   └── VOICE_PIPELINE.md          # Gemini 2.5 Live, Faster-Whisper, Ollama & Piper TTS transliteration
│
├── piper_models/                  # Local Piper TTS neural models (Local Mode)
│   ├── en_US-lessac-medium.onnx
│   └── en_US-lessac-medium.onnx.json
│
├── scripts/                       # Telephony & Database Operations Scripts
│   ├── add_customer.py            # CLI script to insert custom verified customers
│   ├── check_alerts.py            # Twilio account alerts and debugger logger
│   ├── check_numbers.py           # Twilio active phone numbers inspector
│   ├── check_twilio_logs.py       # Twilio call logs and call error debugger
│   ├── check_verified_callers.py  # Twilio verified caller IDs inspector
│   ├── setup_twilio_webhook.py    # Automated Twilio voice webhook updater
│   └── verify_phone_in_twilio.py  # Twilio caller ID verification assistant
│
├── src/
│   ├── config.py                  # Pydantic application settings & dynamic port binding
│   ├── database/                  # Persistence Layer
│   │   ├── db.py                  # SQLite connection, schema initializer & catalog seeder
│   │   ├── customer_repo.py       # Customer registry & phone normalization
│   │   └── booking_repo.py        # Catalog search, orders, and dynamic ETA
│   ├── pipeline/
│   │   └── bot_pipeline.py        # Local voice pipeline orchestrator & VAD loop
│   ├── server/
│   │   ├── telephony_server.py    # FastAPI HTTP server & Twilio WebSocket bridge
│   │   ├── audio_utils.py         # G.711 mu-law <-> 16kHz/24kHz PCM transcoding LUT
│   │   ├── gemini_live_bridge.py  # Gemini 2.5 Live speech-to-speech bridge
│   │   └── templates/
│   │       └── index.html         # Web Management Dashboard & browser call simulator
│   ├── services/
│   │   ├── llm_service.py         # Ollama client, prompts, & tool execution
│   │   ├── stt_service.py         # Multilingual Faster-Whisper STT
│   │   └── tts_service.py         # Piper TTS & Kannada phonetic transliterator
│   └── tools/
│       └── booking_tools.py       # Deterministic tool definitions & dispatchers
│
└── tests/                         # Comprehensive automated test suites
    ├── test_db.py                 # SQLite WAL, repository & catalog tests
    ├── test_server.py             # FastAPI & audio transcoding tests
    ├── test_kannada_flow.py       # Kannada multi-turn conversation tests
    ├── test_customer_flow.py      # English customer conversation tests
    ├── test_voice_engine.py       # Faster-Whisper & Piper TTS validation
    ├── test_gemma_tools.py        # Gemma 3 JSON tool-calling benchmark
    ├── test_clean.py              # Speech text sanitizer tests
    ├── test_hallucination.py      # Whisper silence hallucination filters
    ├── test_local_mic.py          # Local microphone audio test
    ├── test_llm.py                # LLM response unit tests
    └── bench_prompt.py            # LLM latency benchmarking
```

---

## 📄 License
This project is licensed under the MIT License.
