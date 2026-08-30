import io
import numpy as np
from faster_whisper import WhisperModel
from loguru import logger

class STTService:
    def __init__(self, model_size: str = "base.en", device: str = "cpu", compute_type: str = "int8"):
        """
        Initializes faster-whisper.
        model_size options: 'tiny.en' (fastest), 'base.en' (balanced), 'small.en' (accurate).
        """
        logger.info(f"Loading faster-whisper model '{model_size}' on {device} ({compute_type})...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        logger.info("faster-whisper loaded successfully.")

    def transcribe_audio_array(self, audio_array: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe a 16kHz float32 or int16 numpy audio array.
        """
        # Ensure float32 normalized to [-1.0, 1.0]
        if audio_array.dtype == np.int16:
            audio_array = audio_array.astype(np.float32) / 32768.0
        
        segments, info = self.model.transcribe(
            audio_array,
            beam_size=1,            # 1 for lowest latency greedy decoding
            language="en",
            vad_filter=True         # Built-in Silero VAD to skip silence
        )
        
        text = " ".join([segment.text.strip() for segment in segments])
        return text.strip()

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> str:
        """
        Transcribe raw WAV bytes. Faster-whisper automatically handles sample-rate conversion (e.g. 22050Hz -> 16000Hz).
        """
        buffer = io.BytesIO(wav_bytes)
        segments, info = self.model.transcribe(
            buffer,
            beam_size=1,
            language="en",
            vad_filter=True
        )
        text = " ".join([segment.text.strip() for segment in segments])
        return text.strip()
