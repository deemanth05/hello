from src.services.tts_service import TTSService
from src.services.stt_service import STTService

def test_tts_and_stt():
    test_phrase = "Welcome to DMart Express. How can I help you today?"
    print(f"\n1. Original Spoken Text: '{test_phrase}'")
    
    # 1. Test TTS
    print("Testing Piper TTS synthesis...")
    tts = TTSService()
    wav_bytes = tts.synthesize_wav_bytes(test_phrase)
    print(f"Generated {len(wav_bytes)} bytes of WAV audio.")
    assert len(wav_bytes) > 44, "Audio file is empty!"
    
    # Save a test file you can play and listen to!
    with open("piper_output_test.wav", "wb") as f:
        f.write(wav_bytes)
    print("Saved audio to 'piper_output_test.wav'.")

    # 2. Test STT
    print("\n2. Testing faster-whisper STT on the generated audio...")
    stt = STTService(model_size="base.en")
    transcription = stt.transcribe_wav_bytes(wav_bytes)
    print(f"Transcribed Text: '{transcription}'")
    
    assert len(transcription) > 0, "STT transcription was empty!"
    print("\nPiper TTS & faster-whisper STT loopback verified successfully!")

if __name__ == "__main__":
    test_tts_and_stt()
