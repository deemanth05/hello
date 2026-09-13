# System Architecture & Technical Design

The **DMart Express Voice-AI Telephony System** is an ultra-low-latency, bilingual (Kannada & English) conversational AI platform designed for automated phone ordering. It supports both a **100% local, zero-API-cost inference stack** and a **cloud-native Gemini 2.5 Multimodal Live bridge**.

---

## 1. High-Level Architecture

The system operates across three decoupled tiers: **Telephony & Network Edge**, **Audio Processing & Voice Engine**, and the **Business Logic & Persistence Layer**.

```mermaid
graph TD
    subgraph "Telephony Tier"
        Caller[Customer Phone Call] <-->|PSTN| Twilio[Twilio Voice Gateway]
        Twilio <-->|Webhook POST /voice/incoming| FastAPIServer[FastAPI Telephony Server]
        Twilio <-->|Bi-directional WebSocket /voice/stream| FastAPIServer
    end

    subgraph "Inference Modes"
        FastAPIServer -->|Local Mode| LocalPipeline[VoiceBotPipeline]
        FastAPIServer -->|Cloud Mode| GeminiLive[Gemini 2.5 Live Bridge]
    end

    subgraph "Local Voice Engine"
        LocalPipeline -->|8kHz -> 16kHz PCM| VAD[Silero / Energy VAD]
        VAD -->|Segmented Audio| STT[Faster-Whisper STT]
        STT -->|Transcript| LLM[Ollama Gemma 3 / Qwen 2.5]
        LLM -->|Kannada Text| Translit[Phonetic Transliterator]
        Translit -->|Latin Phonemes| TTS[Piper TTS ONNX]
        TTS -->|16kHz PCM -> 8kHz u-law| AudioTranscoder[Audio Transcoder]
        AudioTranscoder -->|20ms Audio Chunks| FastAPIServer
    end

    subgraph "Data & Tool Tier"
        LLM <-->|Function Calling| Tools[Store Tools Dispatcher]
        GeminiLive <-->|Native Tools| Tools
        Tools <--> CustomerRepo[Customer Repository]
        Tools <--> BookingRepo[Order & Catalog Repository]
        CustomerRepo <--> SQLite[(SQLite WAL DB)]
        BookingRepo <--> SQLite
    end
```

---

## 2. Audio Processing & Transcoding Pipeline

Twilio Media Streams exchange audio via the **ITU-T G.711 $\mu$-law standard at 8,000 Hz (8kHz)** formatted in 20ms base64-encoded chunks (160 bytes each). Modern speech-to-text and text-to-speech engines expect linear 16-bit PCM at 16,000 Hz (16kHz) or 24,000 Hz (24kHz).

### Audio Transcoding Specification

| Direction | Source Format | Target Format | Processing Mechanism |
| :--- | :--- | :--- | :--- |
| **Inbound (Caller $\to$ AI)** | 8kHz G.711 $\mu$-law (8-bit) | 16kHz Linear PCM (float32) | Look-up table (LUT) $\mu$-law decoding $\to$ Fast linear interpolation resampling |
| **Outbound Local (AI $\to$ Caller)** | 16kHz Linear PCM (WAV) | 8kHz G.711 $\mu$-law (8-bit) | Linear interpolation downsampling $\to$ 65,536-entry nearest-neighbor $\mu$-law LUT |
| **Outbound Gemini (AI $\to$ Caller)** | 24kHz Linear PCM (16-bit) | 8kHz G.711 $\mu$-law (8-bit) | Linear interpolation downsampling $\to$ $\mu$-law LUT |

### Acoustic Echo Suppression & Turn Taking
1. **Initial Tone Discard**: Twilio trial calls generate initial DTMF keypress tones. The server ignores inbound audio for the first 1.0 second of stream connection.
2. **Duplex Echo Suppression**: When the bot audio sender worker is actively writing audio chunks to Twilio, the inbound audio buffer ignores microphone packets. This prevents acoustic loudspeaker bounce from being recognized as caller speech.
3. **Buffer Purging**: Once bot playback completes, the VAD state and audio buffers are reset cleanly before caller speech detection resumes.

---

## 3. Bilingual Kannada & English Engine

The system is built specifically for Kannada-speaking regions (e.g., Bengaluru, Karnataka) and handles code-switching (Kanglish).

```
                      ┌──────────────────────┐
                      │ Caller Speech Audio  │
                      └──────────┬───────────┘
                                 │
                                 ▼
                     Faster-Whisper STT (base)
             [Kannada & English Auto-detection: 'kn'/'en']
                                 │
                                 ▼
               Transcript: "ನನಗೆ 2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಬೇಕು"
                                 │
                                 ▼
                      Local LLM (Gemma 3)
                   Tool: search_catalog("ಹಾಲು")
                     Returns: Amul Taaza Milk
                                 │
                                 ▼
              Kannada Spoken Text Response:
       "ಖಂಡಿತ, ಅಮೂಲ್ ಹಾಲು ಲಭ್ಯವಿದೆ. ದಯವಿಟ್ಟು ಖಚಿತಪಡಿಸಿ."
                                 │
                                 ▼
                   Phonetic Transliterator
              kannada_to_phonetic_latin()
         Maps Kannada script (U+0C80..U+0CFF)
           to phonetic Latin phoneme string:
          "khandita, amool haalu labhyavide..."
                                 │
                                 ▼
                     Piper TTS (ONNX)
        Synthesizes fluent audio matching Indian cadence
```

---

## 4. Deterministic Caller ID Resolution

When an inbound call arrives at `/voice/incoming`, Twilio transmits caller metadata, including the E.164 phone number (`From`).

1. **Registered Customer**:
   - The phone number is normalized to 10 digits and checked in `customers`.
   - The AI identifies the caller immediately by name (*"ನಮಸ್ಕಾರ Rahul Sharma, ಡಿಮಾರ್ಟ್ ಎಕ್ಸ್‌ಪ್ರೆಸ್‌ಗೆ ಸ್ವಾಗತ!"*).
   - The LLM's system prompt is injected with the customer's pre-registered delivery address and ID.
   - The AI **never asks** for phone number or address during the call.
2. **Unregistered Customer**:
   - Number not found in database.
   - AI greets politely and prompts for name and delivery address.
   - When provided, the LLM atomically executes `register_caller`.
   - The customer profile is created in SQLite, and the call proceeds directly into ordering without restarting.

---

## 5. Dual-Mode Architecture

The project can switch dynamically between two backends based on environment configuration:

### A. 100% Local Inference Mode (Default)
- **Zero API Costs**: No external subscriptions or network latency dependencies.
- **Components**:
  - **STT**: `faster-whisper` (multilingual `base`, int8 CPU/GPU with Silero VAD).
  - **LLM**: Local `ollama` instance (`gemma3:latest` or `qwen2.5:7b`).
  - **TTS**: `piper-tts` (`en_US-lessac-medium` ONNX model).
- **Offline Capable**: Runs completely locally on consumer hardware.

### B. Gemini 2.5 Multimodal Live Mode (Cloud Native)
- **Sub-500ms Turnaround**: Native Speech-to-Speech bi-directional WebSocket connection via `google-genai` SDK.
- **Barge-in Support**: Gemini native acoustic barge-in detects caller interruption and flushes the Twilio audio queue automatically.
- **Activated By**: Specifying `GEMINI_API_KEY` in `.env`.
