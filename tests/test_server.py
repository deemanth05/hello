import sys
import numpy as np
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.server.telephony_server import app
from src.server.audio_utils import decode_mulaw, encode_mulaw, resample_audio, wav_bytes_to_mulaw8k
from src.services.tts_service import TTSService

client = TestClient(app)

def test_telephony_server_and_audio():
    print("\n--- Testing Telephony Server Endpoints ---")
    
    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    print("[OK] Health endpoint verified:", data)

    # 2. Customers endpoint
    res = client.get("/api/customers")
    assert res.status_code == 200
    customers = res.json()["customers"]
    assert len(customers) > 0
    print(f"[OK] Customers API returned {len(customers)} registered customers.")

    # 3. Incoming Voice Webhook (TwiML)
    res = client.post("/voice/incoming", data={"From": "+919876543210", "CallSid": "CA12345"})
    assert res.status_code == 200
    assert "xml" in res.headers["content-type"]
    xml_content = res.text
    assert "<Stream" in xml_content
    assert "+919876543210" in xml_content
    print("[OK] Twilio Voice webhook returned valid TwiML with Stream URL.")

    # 4. In-call / Web Registration Endpoint
    new_phone = "+919555444333"
    res = client.post("/api/register", json={
        "phone": new_phone,
        "name": "Kavita Rao",
        "address": "Villa 14, Prestige Silver Oak, Whitefield"
    })
    assert res.status_code == 200
    reg_data = res.json()
    assert reg_data["success"] is True
    print(f"[OK] Registration API registered: {reg_data['name']} ({reg_data['phone_number']})")

    # 5. Audio Transcoding Tests (ITU-T G.711 mu-law <-> PCM float32)
    print("\n--- Testing Audio Transcoding Utilities ---")
    orig_pcm = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 8000)).astype(np.float32) * 0.8
    mulaw = encode_mulaw(orig_pcm)
    assert len(mulaw) == 8000
    
    decoded_pcm = decode_mulaw(mulaw)
    assert len(decoded_pcm) == 8000
    # Check low reconstruction error
    max_error = np.max(np.abs(orig_pcm - decoded_pcm))
    assert max_error < 0.05, f"Mu-law quantization error too high: {max_error}"
    print(f"[OK] G.711 mu-law encode/decode verified (Max quant error: {max_error:.4f}).")

    # 6. Audio Resampling (8kHz -> 16kHz -> 8kHz)
    resampled_16k = resample_audio(orig_pcm, orig_sr=8000, target_sr=16000)
    assert len(resampled_16k) == 16000
    print("[OK] Fast audio resampling 8kHz -> 16kHz verified.")

    # 7. WAV to 8kHz mu-law transcoding
    tts = TTSService()
    wav_bytes = tts.synthesize_wav_bytes("Hello from DMart Express.")
    mulaw_out = wav_bytes_to_mulaw8k(wav_bytes)
    assert len(mulaw_out) > 0
    print(f"[OK] Synthesized WAV to 8kHz mu-law streaming payload verified ({len(mulaw_out)} bytes).")

    print("\n[PASSED] ALL TELEPHONY SERVER AND AUDIO TRANSCODING TESTS PASSED!")

if __name__ == "__main__":
    test_telephony_server_and_audio()
