import io
import numpy as np
from typing import Optional
from faster_whisper import WhisperModel
from loguru import logger
from src.config import settings

def is_hallucination(text: str) -> bool:
    """Detects Whisper silence hallucinations such as repeated characters or low-entropy loops."""
    if not text or len(text.strip()) < 2:
        return True
    clean = text.strip()
    import re
    # 1. Repeated single character runs (e.g. "aaaaa..." or ".....")
    if re.search(r"(.)\1{4,}", clean):
        return True
    return False

class STTService:
    def __init__(self, model_size: Optional[str] = None, device: str = "cpu", compute_type: str = "int8"):
        """
        Initializes faster-whisper multilingual model for Kannada & English.
        model_size options: 'tiny', 'base' (default), 'small', 'medium'.
        """
        self.model_size = model_size or getattr(settings, "STT_MODEL_SIZE", "base")
        logger.info(f"Loading multilingual faster-whisper model '{self.model_size}' on {device} ({compute_type})...")
        self.model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
        logger.info("Multilingual faster-whisper loaded successfully.")

    def transcribe_audio_array(self, audio_array: np.ndarray, sample_rate: int = 16000, language: Optional[str] = None) -> str:
        """
        Transcribe a 16kHz float32 or int16 numpy audio array with Kannada / English auto-detection.
        """
        if audio_array.dtype == np.int16:
            audio_array = audio_array.astype(np.float32) / 32768.0
        
        segments, info = self.model.transcribe(
            audio_array,
            beam_size=2,
            language=language,
            condition_on_previous_text=False,
            temperature=0.0
        )
        
        text = " ".join([segment.text.strip() for segment in segments])
        # Filter out CJK/Korean hallucinations
        import re
        text = re.sub(r"[\u3000-\u9fff\uac00-\ud7af]+", "", text)
        text = re.sub(r"^[,.\s\-_]+", "", text).strip()
        
        logger.info(f"Whisper STT output: '{text}' (lang={info.language} prob={info.language_probability:.2f})")
        
        if is_hallucination(text):
            return ""
        return text

    def transcribe_wav_bytes(self, wav_bytes: bytes, language: Optional[str] = None) -> str:
        """
        Transcribe raw WAV bytes.
        """
        buffer = io.BytesIO(wav_bytes)
        lang = language or getattr(settings, "STT_LANGUAGE", None)
        segments, info = self.model.transcribe(
            buffer,
            beam_size=1,
            language=lang,
            vad_filter=True
        )
        text = " ".join([segment.text.strip() for segment in segments])
        return text.strip()
