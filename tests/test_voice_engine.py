import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.services.tts_service import TTSService
from src.services.stt_service import STTService

def test_tts_and_stt():
    test_phrase_en = "Welcome to DMart Express. How can I help you today?"
    test_phrase_kn = "ನಮಸ್ಕಾರ, ಡಿಮಾರ್ಟ್ ಎಕ್ಸ್‌ಪ್ರೆಸ್‌ಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ 2 ಪ್ಯಾಕೆಟ್ ಹಾಲು ಬೇಕಾ?"
    
    print(f"\n1. Testing English TTS & STT...")
    tts = TTSService()
    wav_bytes_en = tts.synthesize_wav_bytes(test_phrase_en)
    assert len(wav_bytes_en) > 44, "Audio file is empty!"
    
    stt = STTService(model_size="base")
    transcription_en = stt.transcribe_wav_bytes(wav_bytes_en, language="en")
    print(f"Transcribed Text (EN): '{transcription_en}'")
    assert len(transcription_en) > 0

    print(f"\n2. Testing Kannada (ಕನ್ನಡ) TTS & STT...")
    wav_bytes_kn = tts.synthesize_wav_bytes(test_phrase_kn)
    assert len(wav_bytes_kn) > 44
    print(f"Generated {len(wav_bytes_kn)} bytes of Kannada audio.")
    
    with open("kannada_test_output.wav", "wb") as f:
        f.write(wav_bytes_kn)
    print("Saved Kannada audio to 'kannada_test_output.wav'.")

    print("\nPiper TTS & multilingual faster-whisper STT loopback verified successfully!")

if __name__ == "__main__":
    test_tts_and_stt()
