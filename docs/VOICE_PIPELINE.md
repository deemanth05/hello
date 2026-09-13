# Voice AI Pipeline & Model Architecture

This document specifies the voice inference components, audio processing pipelines, model configurations, transliteration mechanics, and real-time streaming architectures across both local and cloud deployment modes.

---

## 1. Dual Pipeline Overview

The DMart Express Voice AI system operates in two distinct operational modes:

| Dimension | Cloud Mode (Default & Render Production) | Local Pipeline Mode (Edge / Self-Hosted) |
| :--- | :--- | :--- |
| **Engine** | Gemini 2.5 Multimodal Live API (`gemini-2.5-flash-native-audio-latest`) | Decoupled Cascade: Faster-Whisper + Ollama + Piper TTS |
| **Architecture** | Native Speech-to-Speech (S2S) via Bidirectional WebSocket | Pipeline: Audio Frame $\to$ STT $\to$ LLM $\to$ Phonetic Transliteration $\to$ TTS |
| **Latency** | **< 500 ms** (streamed 20ms chunks) | ~1.5 - 2.8 s (sequential inference turn) |
| **RAM Footprint** | **~90 MB** (zero local weights) | ~4 GB - 8 GB (Whisper int8 + Gemma 3 4B/8B + Piper ONNX) |
| **Barge-In Handling** | Native acoustic interruption detection (`sc.interrupted`) | Energy RMS Voice Activity Detection (VAD) |
| **Voice Persona** | `Aoede` (Google Gemini Native Speech Voice) | `en_US-lessac-medium` via Phonetic Kannada Transliteration |

---

## 2. Cloud-Native Speech-to-Speech: Gemini 2.5 Live Bridge

The cloud pipeline is implemented in [`src/server/gemini_live_bridge.py`](file:///c:/Users/deema/Desktop/hello/src/server/gemini_live_bridge.py). It establishes a persistent, bi-directional asynchronous session with Google's Gemini 2.5 Live API over WebSocket.

### Live Session Configuration
- **Model**: `gemini-2.5-flash-native-audio-latest`
- **Response Modality**: `response_modalities=["AUDIO"]`
- **Thinking Delay**: `thinking_config=types.ThinkingConfig(thinking_budget=0)` (zero thinking delay to guarantee immediate real-time speech response)
- **Voice Preset**: `speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")))`
- **Dynamic System Instruction**: Injected per-call via `build_gemini_instruction(caller_phone)` based on whether the caller is pre-registered in SQLite.
- **Tools**: Declared via `GEMINI_TOOLS` (`search_catalog`, `check_stock`, `place_order`, `register_caller`).

### Audio Transformation Pipelines
```
[ Twilio Trunk (8kHz G.711 μ-law) ]
                │
                ▼
        decode_mulaw() ──> float32 (8kHz)
                │
                ▼
        resample_audio(8000 -> 16000)
                │
                ▼
    Accumulate 5 frames (100ms)
                │
                ▼
    send_realtime_input(media=types.Blob(mime_type="audio/pcm;rate=16000"))
                │
                ▼
    [ Gemini 2.5 Live API ]
                │
                ▼
    sc.model_turn.parts[].inline_data (24kHz 16-bit PCM)
                │
                ▼
        resample_audio(24000 -> 8000)
                │
                ▼
        encode_mulaw() ──> 8kHz μ-law bytes
                │
                ▼
    Chunked into 160 bytes (20ms packets) -> outbound_audio_queue
                │
                ▼
    Paced at 18ms intervals to Twilio WebSocket (event: "media")
```

### Acoustic Barge-in & Interruption
When Gemini's acoustic model detects caller speech while the bot is speaking:
1. Gemini issues a server event with `sc.interrupted == True`.
2. The server drains and empties the `outbound_audio_queue` immediately.
3. The server sends `{"event": "clear", "streamSid": stream_sid}` to Twilio, clearing Twilio's audio playback buffer and stopping voice playback in the caller's ear in under 50ms.

### Real-Time Tool Calling Loop
1. When Gemini decides to query the catalog or commit an order, it sends a `response.tool_call` containing one or more `function_calls`.
2. The server dispatches the call through `execute_tool_call(call.name, call.args, default_phone=caller_phone)`.
3. The JSON result is posted back into the active WebSocket session:
   ```python
   await session.send_tool_response(
       function_responses=[
           types.FunctionResponse(
               name=call.name,
               id=call.id,
               response={"result": res}
           )
       ]
   )
   ```
4. Gemini immediately resumes speaking natural Kannada, incorporating the tool result into its verbal reply.

---

## 3. Local Speech-to-Text (STT): Faster-Whisper

In Local Mode ([`src/services/stt_service.py`](file:///c:/Users/deema/Desktop/hello/src/services/stt_service.py)), speech recognition runs on CPU or local GPU using `faster-whisper` (CTranslate2).

### Configuration
- **Model**: `base` (multilingual), configurable via `STT_MODEL_SIZE` in `.env`.
- **Compute Type**: `int8` quantization.
- **Decoding Parameters**:
  - `beam_size=2`
  - `temperature=0.0`
  - `condition_on_previous_text=False` (prevents hallucination cascading)
  - Auto-language detection between Kannada (`kn`) and English (`en`).

### Hallucination Protection
Whisper models can loop or emit arbitrary characters during ambient silence:
1. `is_hallucination`: Discards text with fewer than 2 characters.
2. Repetition regex: Flags single characters repeated 4+ times (`re.search(r"(.)\1{4,}", clean)`).
3. Non-Indic/CJK stripping: Removes Korean/Chinese character blocks (`re.sub(r"[\u3000-\u9fff\uac00-\ud7af]+", "", text)`).

---

## 4. Local Language Model (LLM): Ollama

In Local Mode ([`src/services/llm_service.py`](file:///c:/Users/deema/Desktop/hello/src/services/llm_service.py)), reasoning is powered by Ollama running **Gemma 3 (`gemma3:latest`)** or **Qwen 2.5 (`qwen2.5:7b`)**.

### Gemma 3 Tool-Calling Mechanics
Gemma 3 models may not always use native Ollama JSON tool tags. The service supports dual-mode extraction:
1. **Native Tool Detection**: Intercepts `tool_calls` structure when available.
2. **Prompt-based JSON Detection**: Inspects output for Markdown code blocks (````json { ... } ````) or raw JSON objects using `_extract_json_tool_call`.
3. **Turn Loop**: Executes the tool call via `execute_tool_call`, injects the result into conversation history with role `user` (`[TOOL RESULT for ...]`), and requests the final spoken response.

### Conversational Text Sanitization (`clean_speech_text`)
Raw LLM outputs containing Markdown or JSON structures must not be sent to a speech synthesizer. `clean_speech_text`:
- Strips code blocks, curly brackets, square brackets, and quotation marks.
- Strips Markdown characters (`*`, `#`, `_`, `~`, `\``).
- Removes emojis and control characters while preserving Kannada Unicode (U+0C80..U+0CFF) and standard Latin characters.
- Normalizes punctuation and spacing for natural phrasing.

---

## 5. Local Text-to-Speech (TTS): Piper TTS

Audio synthesis runs locally via `piper-tts` ([`src/services/tts_service.py`](file:///c:/Users/deema/Desktop/hello/src/services/tts_service.py)) using the `en_US-lessac-medium` ONNX neural acoustic model.

### Automatic Model Download
On initial boot, `_ensure_model_downloaded()` retrieves:
- ONNX model: `en_US-lessac-medium.onnx` from HuggingFace
- Config JSON: `en_US-lessac-medium.onnx.json` from HuggingFace
into the local `piper_models/` directory.

### Phonetic Kannada-to-Latin Transliteration
Because Piper's neural acoustic model is English-based, native Kannada Unicode cannot be fed directly to the synthesizer. The custom rule engine `kannada_to_phonetic_latin` maps Kannada script into natural Latin phonemes:

1. **Vowels**:
   - `ಅ` $\to$ `a`, `ಆ` $\to$ `aa`, `ಇ` $\to$ `i`, `ಈ` $\to$ `ee`, `ಉ` $\to$ `u`, `ಊ` $\to$ `oo`
   - `ಋ` $\to$ `ru`, `ಎ` $\to$ `e`, `ಏ` $\to$ `ae`, `ಐ` $\to$ `ai`, `ಒ` $\to$ `o`, `ಓ` $\to$ `o`, `ಔ` $\to$ `ou`
   - `ಅಂ` $\to$ `am`, `ಅಃ` $\to$ `aha`
2. **Consonants & Matras**:
   - Inherent `a` is attached to consonants (`ಕ` $\to$ `ka`, `ತ` $\to$ `tha`).
   - Matras (vowel signs) replace the inherent vowel (`ಕಾ` $\to$ `kaa`, `ಕಿ` $\to$ `ki`, `ಕು` $\to$ `ku`).
   - The Virama (`್`) strips the inherent vowel completely (`ಕ್` $\to$ `k`, `ತ್` $\to$ `th`).
3. **Anusvara & Visarga**:
   - `ಂ` $\to$ `m`, `ಃ` $\to$ `h`.

This phonetic mapping allows the neural synthesizer to pronounce melodic, natural-sounding spoken Kannada with zero cloud dependencies.
