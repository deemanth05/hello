import numpy as np
import base64
import io
import wave
from typing import Tuple

# 1. Standard ITU-T G.711 mu-law decoding table (256 reconstruction levels)
_MULAW_TO_LINEAR = np.zeros(256, dtype=np.int16)
for i in range(256):
    u = ~i & 0xFF
    t = ((u & 0x0F) << 3) + 0x84
    t <<= ((u & 0x70) >> 4)
    _MULAW_TO_LINEAR[i] = np.int16((0x84 - t) if (u & 0x80) else (t - 0x84))

# 2. Optimal nearest-match 16-bit Linear PCM to 8-bit mu-law encoding LUT
_levels = _MULAW_TO_LINEAR.astype(np.int32)
_pcm_range = np.arange(-32768, 32768, dtype=np.int32)
# Fast binary search / nearest index mapping across all 65536 possible PCM values
_LINEAR_TO_MULAW = np.abs(_pcm_range[:, None] - _levels[None, :]).argmin(axis=1).astype(np.uint8)

def decode_mulaw(mulaw_bytes: bytes) -> np.ndarray:
    """
    Decodes 8kHz mu-law bytes into 8kHz float32 numpy array in range [-1.0, 1.0].
    """
    if not mulaw_bytes:
        return np.zeros(0, dtype=np.float32)
    indices = np.frombuffer(mulaw_bytes, dtype=np.uint8)
    pcm16 = _MULAW_TO_LINEAR[indices]
    return pcm16.astype(np.float32) / 32768.0

def encode_mulaw(pcm_float: np.ndarray) -> bytes:
    """
    Encodes float32 numpy array [-1.0, 1.0] into 8kHz mu-law bytes.
    """
    if len(pcm_float) == 0:
        return b""
    clipped = np.clip(pcm_float, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int32)
    indices = pcm16 + 32768
    mulaw_bytes = _LINEAR_TO_MULAW[indices].tobytes()
    return mulaw_bytes

def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Resamples 1D float32 audio from orig_sr to target_sr using fast linear interpolation.
    """
    if orig_sr == target_sr or len(audio) == 0:
        return audio
    duration = len(audio) / orig_sr
    num_target_samples = int(round(duration * target_sr))
    orig_indices = np.linspace(0, len(audio) - 1, num=len(audio))
    target_indices = np.linspace(0, len(audio) - 1, num=num_target_samples)
    return np.interp(target_indices, orig_indices, audio).astype(np.float32)

def wav_bytes_to_mulaw8k(wav_bytes: bytes) -> bytes:
    """
    Converts raw WAV audio bytes (any sample rate) to 8kHz mu-law bytes for Twilio.
    """
    if not wav_bytes:
        return b""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
        
        pcm16 = np.frombuffer(frames, dtype=np.int16)
        if n_channels > 1:
            pcm16 = pcm16.reshape(-1, n_channels)[:, 0]
            
        float_audio = pcm16.astype(np.float32) / 32768.0
        audio_8k = resample_audio(float_audio, orig_sr=sr, target_sr=8000)
        return encode_mulaw(audio_8k)
