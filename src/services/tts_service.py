import os
import urllib.request
from pathlib import Path
from typing import Generator
from piper import PiperVoice
from loguru import logger
from src.config import BASE_DIR

MODELS_DIR = BASE_DIR / "piper_models"
MODEL_NAME = "en_US-lessac-medium"
ONNX_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/{MODEL_NAME}.onnx"
JSON_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/{MODEL_NAME}.onnx.json"

class TTSService:
    def __init__(self):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self.onnx_path = MODELS_DIR / f"{MODEL_NAME}.onnx"
        self.json_path = MODELS_DIR / f"{MODEL_NAME}.onnx.json"
        
        self._ensure_model_downloaded()
        
        logger.info(f"Loading Piper TTS voice from {self.onnx_path}...")
        self.voice = PiperVoice.load(str(self.onnx_path), config_path=str(self.json_path))
        logger.info("Piper TTS loaded successfully.")

    def _ensure_model_downloaded(self):
        if not self.onnx_path.exists():
            logger.info(f"Downloading Piper ONNX model from {ONNX_URL}...")
            urllib.request.urlretrieve(ONNX_URL, str(self.onnx_path))
        if not self.json_path.exists():
            logger.info(f"Downloading Piper config from {JSON_URL}...")
            urllib.request.urlretrieve(JSON_URL, str(self.json_path))

    def synthesize_wav_bytes(self, text: str) -> bytes:
        """Synthesize text to raw WAV / PCM bytes synchronously."""
        import wave
        import io
        
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file)
        
        return buffer.getvalue()

    def synthesize_stream(self, text: str):
        """Yields raw 16-bit PCM bytes for real-time streaming."""
        for chunk in self.voice.synthesize(text):
            yield chunk.audio_int16_bytes
