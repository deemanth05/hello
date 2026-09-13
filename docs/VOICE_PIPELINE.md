# Voice AI Pipeline & Model Architecture

This document outlines the voice inference components, audio processing stages, model configurations, and transliteration mechanics of the system.

---

## 1. Local Speech-to-Text (STT): Faster-Whisper

Speech recognition is handled locally by `faster-whisper`, a reimplementation of OpenAI Whisper using `CTranslate2`.

### Configuration
- **Model Size**: `base` (multilingual), upgradeable to `small` or `medium` via `STT_MODEL_SIZE` in `.env`.
- **Compute Type**: `int8` quantization for high CPU/GPU performance.
- **Sampling Rate**: 16,000 Hz (16kHz), mono float32.
- **VAD (Voice Activity Detection)**: Energy RMS threshold (`0.040`) with Silero VAD filtering.
- **Language Detection**: Auto-detects between Kannada (`kn`) and English (`en`).

### Hallucination Filtering
Whisper models can produce repetitive loops or arbitrary text during long silences. The STT service guards against this with `is_hallucination`:
1. Discards transcripts under 2 characters or composed only of punctuation.
2. Detects character repetition patterns (`re.search(r"(.)\1{4,}", text)`).
3. Strips stray non-indic/CJK unicode characters.

---

## 2. Local Language Model (LLM): Ollama

The system interfaces with a local Ollama server running **Gemma 3 (`gemma3:latest`)** or **Qwen 2.5 (`qwen2.5:7b`)**.

### Gemma 3 Tool-Calling Strategy
While models like Qwen 2.5 support native JSON tools via Ollama's `tools` parameter, Gemma 3 can execute tools through structured prompt instructions. The pipeline supports both:

1. **Native Tool Detection**: Intercepts `tool_calls` array in Ollama's response.
2. **Prompt-based JSON Detection**: Parses raw or markdown-wrapped JSON objects containing `"tool"` and `"arguments"`.
3. **Loop Dispatcher**: Automatically calls `execute_tool_call`, injects the result into the conversation with role `user` (`[TOOL RESULT for ...]`), and asks the LLM for the spoken response.

### Conversational Response Sanitation (`clean_speech_text`)
LLM outputs often contain markdown formatting or technical characters that sound unnatural when read by a TTS synthesizer. Before sending text to Piper TTS:
- Strips code blocks and JSON objects.
- Strips markdown characters (`*`, `#`, `_`, `~`, `\``).
- Removes emojis and non-speech symbols.
- Preserves Kannada Unicode (U+0C80..U+0CFF) and English letters/numbers.
- Cleans whitespace and trailing punctuation.

---

## 3. Local Text-to-Speech (TTS): Piper TTS

Audio synthesis runs locally via `piper-tts` using the `en_US-lessac-medium` ONNX neural acoustic model.

### Phonetic Kannada-to-Latin Transliteration
Piper's English ONNX model produces high-quality speech for English, but cannot read native Kannada Unicode characters directly. The system features a custom phonetic mapper (`kannada_to_phonetic_latin` in `src/services/tts_service.py`):

1. **Vowels**:
   - `ಅ` $\to$ `a`, `ಆ` $\to$ `aa`, `ಇ` $\to$ `i`, `ಈ` $\to$ `ee`, `ಉ` $\to$ `u`, `ಊ` $\to$ `oo`, `ಎ` $\to$ `e`, `ಏ` $\to$ `ae`, `ಐ` $\to$ `ai`, `ಒ` $\to$ `o`, `ಓ` $\to$ `o`.
2. **Consonants & Virama**:
   - Consonants carry an inherent `a` (e.g., `ಕ` $\to$ `ka`).
   - When followed by a vowel sign (matra, e.g. `ಾ`, `ಿ`, `ು`), the inherent `a` is dropped and replaced with the vowel phoneme (`ಕಾ` $\to$ `kaa`, `ಕಿ` $\to$ `ki`).
   - When followed by the Virama (`್`), the inherent vowel is dropped completely (`ಕ್` $\to$ `k`).
3. **Anusvara & Visarga**:
   - `ಂ` $\to$ `m`, `ಃ` $\to$ `h`.

This enables Piper TTS to pronounce fluent, melodic spoken Kannada with zero API latency or internet connectivity.

---

## 4. Cloud-Native Mode: Gemini 2.5 Multimodal Live Bridge

When `GEMINI_API_KEY` is present in `.env`, the telephony server activates the Gemini 2.5 Flash Native Audio engine (`gemini-2.5-flash-native-audio-latest`).

### Architectural Highlights
- **Direct Speech-to-Speech**: Eliminates separate STT and TTS stages. Inbound audio is sent directly to Gemini, and Gemini returns 24kHz PCM audio frames.
- **Sub-500ms End-to-End Latency**: The model starts producing voice packets before the entire sentence has finished generating.
- **Native Interruption Handling**: Built-in acoustic barge-in signals when the caller speaks over the bot (`sc.interrupted`), prompting the server to send an immediate `{"event": "clear"}` message to Twilio.
- **Dynamic Tool Execution**: Gemini issues tool requests (`response.tool_call`), the server executes them against SQLite, and sends `session.send_tool_response()` over the live stream.
