# DMart Express - Voice-AI Telephony System (ಕನ್ನಡ & English)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0+-009688.svg)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-gemma3%20%7C%20qwen2.5-black.svg)](https://ollama.com/)
[![Twilio](https://img.shields.io/badge/Twilio-Media%20Streams-F22F46.svg)](https://www.twilio.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade, bilingual (**Kannada / ಕನ್ನಡ & English**) automated phone ordering system for supermarkets and grocery stores. Features **100% local inference** (zero per-minute API costs) with a cloud-native **Gemini 2.5 Live Multimodal** fallback, deterministic caller identification, natural language grocery catalog search, dynamic delivery arrival times (ETA), and real-time bi-directional Twilio telephony integration.

---

## 📚 Complete Documentation Index

| Document | Description |
| :--- | :--- |
| **[System Architecture](docs/ARCHITECTURE.md)** | Technical design, audio transcoding pipelines (8kHz $\mu$-law $\leftrightarrow$ 16kHz PCM), and sequence diagrams |
| **[API Reference](docs/API_REFERENCE.md)** | Full specification of REST endpoints, Twilio webhook, and WebSocket streaming events |
| **[Database & Models](docs/DATABASE.md)** | SQLite WAL schema, table definitions, phone normalization, and semantic grocery synonyms |
| **[Voice AI Pipeline](docs/VOICE_PIPELINE.md)** | Faster-Whisper STT, Ollama LLM integration, Piper TTS phonetic transliteration, and Gemini Live |
| **[Tool Calling Reference](docs/TOOLS_REFERENCE.md)** | AI function-calling specifications (`search_catalog`, `place_order`, `register_caller`, etc.) |
| **[Telephony Setup Guide](docs/TELEPHONY_SETUP.md)** | Step-by-step Twilio setup, Cloudflare Tunnel (`cloudflared.exe`), and ngrok instructions |
| **[Simulator & Testing Guide](docs/SIMULATOR_AND_TESTING.md)** | Local interactive caller simulator (Text & Mic modes) and automated test suites |
| **[Deployment & Operations](docs/DEPLOYMENT_AND_OPERATIONS.md)** | System requirements, systemd/Windows service setup, and performance tuning |

---

## 🌟 Key Highlights

1. **Bilingual Conversational AI (Kannada & English)**:
   - Understands native Kannada script, colloquial phrasing, and Kanglish (e.g. *"ನನಗೆ 2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಮತ್ತು ಒಂದು ಬ್ರೆಡ್ ಬೇಕು"*, *"ಚಹಾ ಪುಡಿ ಮತ್ತು ಸಕ್ಕರೆ"*).
   - Powered by local **`gemma3:latest`** (or `qwen2.5:7b`) with universal function calling.
   - Proprietary phonetic transliteration engine enabling **Piper TTS** to speak fluent Kannada with natural cadence.
   - Multilingual **Faster-Whisper** (`base` / `small`) with Silero VAD and hallucination suppression.

2. **Deterministic Caller Recognition**:
   - **Registered Customers**: Welcomed by name in Kannada (*"ನಮಸ್ಕಾರ {name}, ಡಿಮಾರ್ಟ್ ಎಕ್ಸ್‌ಪ್ರೆಸ್‌ಗೆ ಸ್ವಾಗತ!"*). The AI **never asks** for phone number or address—it automatically pulls saved details from SQLite.
   - **Unregistered Callers**: Welcomed, prompted for their name and delivery address, atomically registered via `register_caller`, and transitioned seamlessly to order taking.

3. **Dynamic Delivery ETA**:
   - Computes delivery arrival windows dynamically based on current time (e.g. *"30 ರಿಂದ 40 ನಿಮಿಷಗಳಲ್ಲಿ, ಸುಮಾರು 9:45 PM ಗೆ ಬರುತ್ತದೆ"*).
   - Generates a full spoken summary in Kannada: items ordered, total amount in rupees (ರೂಪಾಯಿ), delivery address, and expected arrival time.

4. **100% Local Inference Stack (Zero API Costs)**:
   - **Local STT**: `faster-whisper` (`base` / `small`, int8 compute on CPU or GPU).
   - **Local LLM**: `ollama` (`gemma3:latest` / `qwen2.5:7b`).
   - **Local TTS**: `piper-tts` (`en_US-lessac-medium` ONNX).

5. **Cloud-Native Fallback (Gemini 2.5 Live)**:
   - Set `GEMINI_API_KEY` to enable Gemini 2.5 Flash Native Audio for direct Speech-to-Speech streaming with sub-500ms turnaround and acoustic barge-in.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) installed and running:
  ```bash
  ollama run gemma3:latest
  ```

### 2. Installation
Clone the repository and install dependencies in a virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Initialize Database & Run Tests
```powershell
# Run database and repository tests
python tests/test_db.py

# Run telephony server and audio transcoding tests
python tests/test_server.py

# Run Kannada multi-turn voice-AI test suite
python tests/test_kannada_flow.py
```

### 4. Launch the Interactive Phone Simulator
Test without making a real telephone call:
```powershell
python run_simulator.py
```
- Select **[1] Registered Customer** or **[3] Unregistered Caller**.
- Choose **Text Chat Mode** (with speaker playback) or **Live Microphone Voice Mode** to speak naturally in Kannada!

---

## 📞 Live Telephony Deployment

1. **Start the Telephony Server**:
   ```powershell
   python -m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8765
   ```

2. **Expose with Bundled Cloudflare Tunnel**:
   ```powershell
   .\cloudflared.exe tunnel --url http://localhost:8765
   ```
   *(Or with ngrok: `ngrok http 8765`)*

3. **Configure Twilio Voice Webhook**:
   - In the [Twilio Console](https://console.twilio.com/), set your Phone Number's Voice Webhook to:
     ```
     https://<YOUR_TUNNEL_DOMAIN>/voice/incoming  (HTTP POST)
     ```
   - Or run the automated updater:
     ```powershell
     python scripts/setup_twilio_webhook.py https://<YOUR_TUNNEL_DOMAIN>/voice/incoming
     ```

4. **Make a Call**: Dial your Twilio number from your mobile phone and speak in Kannada!

---

## 📁 Repository Structure

```
hello/
├── README.md                      # Master project overview & documentation hub
├── requirements.txt               # Production Python dependencies
├── .env.example                   # Environment configuration template
├── dmart_store.db                 # SQLite database (customers, catalog, orders)
├── cloudflared.exe                # Bundled Cloudflare Tunnel executable
├── run_simulator.py               # Interactive CLI simulator (Text & Mic voice)
├── test_e2e_call.py               # End-to-end WebSocket client call simulation
│
├── docs/                          # Detailed Technical Documentation
│   ├── ARCHITECTURE.md            # System architecture & audio pipeline design
│   ├── API_REFERENCE.md           # REST & WebSocket telephony protocol reference
│   ├── DATABASE.md                # Schema, models, synonym mapping & pricing rules
│   ├── VOICE_PIPELINE.md          # STT, LLM, Piper transliteration & Gemini Live
│   ├── TOOLS_REFERENCE.md         # Function-calling specifications & schemas
│   ├── TELEPHONY_SETUP.md         # Twilio webhook & Cloudflare/ngrok setup
│   ├── SIMULATOR_AND_TESTING.md   # Testing guide & test suite descriptions
│   └── DEPLOYMENT_AND_OPERATIONS.md # Hardware sizing, services & operations
│
├── piper_models/                  # Local Piper TTS neural models
│   ├── en_US-lessac-medium.onnx
│   └── en_US-lessac-medium.onnx.json
│
├── scripts/
│   └── setup_twilio_webhook.py    # Automated Twilio voice webhook configuration
│
├── src/
│   ├── config.py                  # Pydantic application settings
│   ├── database/                  # Persistence Layer
│   │   ├── db.py                  # SQLite connection & schema initializer
│   │   ├── customer_repo.py       # Customer registry & phone normalization
│   │   └── booking_repo.py        # Catalog search, orders, and dynamic ETA
│   ├── pipeline/
│   │   └── bot_pipeline.py        # Voice pipeline orchestrator & VAD loop
│   ├── server/
│   │   ├── telephony_server.py    # FastAPI HTTP & Twilio WebSocket server
│   │   ├── audio_utils.py         # G.711 mu-law <-> 16kHz PCM transcoding LUT
│   │   └── gemini_live_bridge.py  # Gemini 2.5 Live speech-to-speech fallback
│   ├── services/
│   │   ├── llm_service.py         # Ollama client, prompts, & tool execution
│   │   ├── stt_service.py         # Multilingual Faster-Whisper STT
│   │   └── tts_service.py         # Piper TTS & Kannada phonetic transliterator
│   └── tools/
│       └── booking_tools.py       # JSON tool definitions & dispatchers
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
    └── bench_prompt.py            # LLM latency benchmarking
```

---

## 📄 License
This project is licensed under the MIT License.
