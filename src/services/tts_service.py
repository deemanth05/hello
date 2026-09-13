import os
import urllib.request
import re
import wave
import io
from pathlib import Path
from typing import Generator
from piper import PiperVoice
from loguru import logger
from src.config import BASE_DIR

MODELS_DIR = BASE_DIR / "piper_models"
MODEL_NAME = "en_US-lessac-medium"
ONNX_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/{MODEL_NAME}.onnx"
JSON_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/{MODEL_NAME}.onnx.json"

# Complete Kannada Unicode character map to Latin phonetics
KN_MAP = {
    # Vowels
    'ಅ': 'a', 'ಆ': 'aa', 'ಇ': 'i', 'ಈ': 'ee', 'ಉ': 'u', 'ಊ': 'oo',
    'ಋ': 'ru', 'ಎ': 'e', 'ಏ': 'ae', 'ಐ': 'ai', 'ಒ': 'o', 'ಓ': 'o', 'ಔ': 'ou',
    'ಅಂ': 'am', 'ಅಃ': 'aha',
    # Consonants
    'ಕ': 'ka', 'ಖ': 'kha', 'ಗ': 'ga', 'ಘ': 'gha', 'ಙ': 'nga',
    'ಚ': 'cha', 'ಛ': 'chha', 'ಜ': 'ja', 'ಝ': 'jha', 'ಞ': 'nya',
    'ಟ': 'ta', 'ಠ': 'tha', 'ಡ': 'da', 'ಢ': 'dha', 'ಣ': 'na',
    'ತ': 'tha', 'ಥ': 'thha', 'ದ': 'da', 'ಧ': 'dha', 'ನ': 'na',
    'ಪ': 'pa', 'ಫ': 'pha', 'ಬ': 'ba', 'ಭ': 'bha', 'ಮ': 'ma',
    'ಯ': 'ya', 'ರ': 'ra', 'ಲ': 'la', 'ವ': 'va', 'ಶ': 'sha',
    'ಷ': 'sha', 'ಸ': 'sa', 'ಹ': 'ha', 'ಳ': 'la',
    # Matras (vowel signs)
    'ಾ': 'aa', 'ಿ': 'i', 'ೀ': 'ee', 'ು': 'u', 'ೂ': 'oo', 'ೃ': 'ru',
    'ೆ': 'e', 'ೇ': 'ae', 'ೈ': 'ai', 'ೊ': 'o', 'ೋ': 'o', 'ೌ': 'ou',
    '್': '', # Virama (drops inherent 'a')
    'ಂ': 'm', 'ಃ': 'h'
}

def kannada_to_phonetic_latin(text: str) -> str:
    """
    Converts Kannada Unicode script into phonetic Latin text for natural Piper TTS playback.
    """
    if not text:
        return ""
    # Strip zero-width joiners and hidden chars
    text = re.sub(r'[\u200b-\u200f\u2028-\u202f]', '', text)
    
    res = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in KN_MAP:
            # Check if followed by vowel sign (matra) or virama
            if i + 1 < len(text) and text[i+1] in ['ಾ', 'ಿ', 'ೀ', 'ು', 'ೂ', 'ೃ', 'ೆ', 'ೇ', 'ೈ', 'ೊ', 'ೋ', 'ೌ', '್']:
                base = KN_MAP[ch]
                if base.endswith('a'):
                    base = base[:-1] # Drop inherent 'a'
                matra = KN_MAP[text[i+1]]
                res.append(base + matra)
                i += 2
                continue
            else:
                res.append(KN_MAP[ch])
        else:
            res.append(ch)
        i += 1
    return ''.join(res)

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
        """
        Synthesize text to raw WAV / PCM bytes synchronously.
        Automatically transliterates Kannada Unicode script to phonetic Latin for fluent playback.
        """
        # If text contains Kannada characters (U+0C80..U+0CFF), transliterate to phonetics
        if re.search(r'[\u0C80-\u0CFF]', text):
            phonetic_text = kannada_to_phonetic_latin(text)
        else:
            phonetic_text = text
            
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self.voice.synthesize_wav(phonetic_text, wav_file)
        
        return buffer.getvalue()

    def synthesize_stream(self, text: str):
        """Yields raw 16-bit PCM bytes for real-time streaming."""
        if re.search(r'[\u0C80-\u0CFF]', text):
            phonetic_text = kannada_to_phonetic_latin(text)
        else:
            phonetic_text = text
            
        for chunk in self.voice.synthesize(phonetic_text):
            yield chunk.audio_int16_bytes
