# Simulator & Testing Guide

This project includes a comprehensive suite of automated tests and an interactive local phone call simulator that allows testing without making a real telephone call.

---

## 1. Interactive Local Simulator (`run_simulator.py`)

The simulator provides two interactive modes:

```powershell
.venv\Scripts\python.exe run_simulator.py
```

### Menu Options
When launched, you will see the following menu:
```
============================================================
DMart Express - Local Voice-AI Telephony Simulator
============================================================
Select Caller Profile:
  [1] Registered Customer: Rahul Sharma (+919876543210)
  [2] Registered Customer: Priya Patel (+919812345678)
  [3] Unregistered Caller (+919111222333) - Tests In-Call Registration
  [4] Custom Phone Number
  [5] Run Automated Kannada Tests (ಕನ್ನಡ - gemma3:latest)
  [6] Run Automated English Tests (qwen2.5:7b)
  [0] Exit
```

### Modes

#### A. Text Chat Mode with Audio Playback
- You type prompts in Kannada, Kanglish, or English (e.g. *"ನನಗೆ 2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಬೇಕು"* or *"I want 1 liter oil and sugar"*).
- The AI prints its Kannada response and plays spoken audio through your computer's speakers using Piper TTS.

#### B. Live Microphone Voice Mode
- Uses `sounddevice` to capture your microphone in real-time.
- Buffers speech chunks, applies Energy VAD, runs Faster-Whisper speech recognition, and replies via speakers.

---

## 2. Automated Test Suites

The repository contains 10 targeted test scripts in `tests/`:

### 1. Database & Catalog Repository (`tests/test_db.py`)
Verifies SQLite WAL initialization, phone number normalization, semantic synonym queries, inventory stock deductions, dynamic ETA calculations, and order cancellations.
```powershell
.venv\Scripts\python.exe tests/test_db.py
```

### 2. Telephony Server & Audio Transcoding (`tests/test_server.py`)
Validates FastAPI endpoints (`/health`, `/api/customers`, `/api/products`), TwiML generation on `/voice/incoming`, and G.711 $\mu$-law 8kHz $\leftrightarrow$ 16kHz audio transcoding algorithms.
```powershell
.venv\Scripts\python.exe tests/test_server.py
```

### 3. Multi-turn Kannada Voice AI Flow (`tests/test_kannada_flow.py`)
Tests complete multi-turn conversational flows in Kannada with `gemma3:latest`, verifying:
- Greeting registered customers in Kannada.
- General intent catalog matching (`ಹಾಲು`, `ಅಡುಗೆ ಎಣ್ಣೆ`, `ಚಹಾ ಪುಡಿ`).
- In-call registration of new callers speaking Kannada.
- Order confirmation with ETA and total calculations.
```powershell
.venv\Scripts\python.exe tests/test_kannada_flow.py
```

### 4. English Customer Flow (`tests/test_customer_flow.py`)
Tests English conversational flows and tool-calling with `qwen2.5:7b`.
```powershell
.venv\Scripts\python.exe tests/test_customer_flow.py
```

### 5. Voice Engine & Piper Transliteration (`tests/test_voice_engine.py`)
Validates the Kannada-to-Latin phonetic transliterator, Piper TTS ONNX synthesis, and Faster-Whisper audio transcription.
```powershell
.venv\Scripts\python.exe tests/test_voice_engine.py
```

### 6. Hallucination Suppression (`tests/test_hallucination.py`)
Tests Whisper silence filtering, repeated character loops, and CJK text stripping.
```powershell
.venv\Scripts\python.exe tests/test_hallucination.py
```

### 7. Gemma Tool Calling Benchmark (`tests/test_gemma_tools.py`)
Benchmarks Gemma 3's reliability in outputting valid JSON tool calls.
```powershell
.venv\Scripts\python.exe tests/test_gemma_tools.py
```

### 8. Speech Text Sanitizer (`tests/test_clean.py`)
Verifies that markdown, emojis, stray quotes, and JSON fragments are cleaned before feeding text to TTS.
```powershell
.venv\Scripts\python.exe tests/test_clean.py
```

### 9. Prompt Latency Benchmark (`tests/bench_prompt.py`)
Measures time-to-first-token (TTFT) and total generation latency for Ollama models on CPU/GPU.
```powershell
.venv\Scripts\python.exe tests/bench_prompt.py
```

### 10. End-to-End WebSocket Simulation (`test_e2e_call.py`)
Simulates a live Twilio WebSocket phone call over the internet, transmitting synthesized 20ms $\mu$-law audio packets, verifying inbound greeting reception, streaming caller speech turns, triggering tool calls against SQLite, and measuring time-to-first-audio-byte (TTFB).

```powershell
# 1. Test against local telephony server (default)
.venv\Scripts\python.exe test_e2e_call.py ws://localhost:8765/voice/stream +917676219923

# 2. Test against live Render cloud deployment
.venv\Scripts\python.exe test_e2e_call.py wss://hello-8ct1.onrender.com/voice/stream +917676219923

# 3. Test against Cloudflare Tunnel
.venv\Scripts\python.exe test_e2e_call.py wss://<subdomain>.trycloudflare.com/voice/stream +917676219923
```
Parameters:
- `arg 1` *(optional)*: Target WebSocket URL (defaults to `ws://localhost:8765/voice/stream`).
- `arg 2` *(optional)*: Caller phone number to simulate (defaults to `+919008474173`).
