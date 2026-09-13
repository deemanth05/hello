import asyncio
import numpy as np
import sounddevice as sd
import wave
import io
from src.pipeline.bot_pipeline import VoiceBotPipeline
from src.database.db import init_db

async def run_local_voice_assistant():
    init_db()
    pipeline = VoiceBotPipeline()
    
    print("\n" + "="*60)
    print("LOCAL VOICE AI ASSISTANT READY (DMart Express)")
    print("Speak into your microphone. Say something like:")
    print("  'Do you have Basmati Rice and Milk?'")
    print("  'I want to place an order for 2 packets of milk.'")
    print("Press Ctrl+C to stop.")
    print("="*60 + "\n")
    
    chunk_size = 1600 # 100ms at 16kHz
    sample_rate = 16000
    
    loop = asyncio.get_running_loop()
    audio_queue = asyncio.Queue()

    def mic_callback(indata, frames, time, status):
        """Non-blocking audio callback from sounddevice."""
        if status:
            pass
        # indata is float32 [-1.0, 1.0] mono
        loop.call_soon_threadsafe(audio_queue.put_nowait, indata[:, 0].copy())

    # Open microphone stream at 16kHz mono float32
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', blocksize=chunk_size, callback=mic_callback):
        while True:
            chunk = await audio_queue.get()
            speech_segment = pipeline.process_audio_chunk(chunk)
            
            if speech_segment is not None:
                print("\n[VAD]: Speech detected and completed. Processing turn...")
                reply_wav_bytes = await pipeline.execute_turn(speech_segment)
                
                if reply_wav_bytes:
                    # Play the synthesized response over speakers
                    with wave.open(io.BytesIO(reply_wav_bytes), "rb") as wf:
                        data = wf.readframes(wf.getnframes())
                        audio_out = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                        sd.play(audio_out, samplerate=wf.getframerate())
                        sd.wait() # Wait until audio playback finishes before listening again
                    print("Listening again...")

if __name__ == "__main__":
    try:
        asyncio.run(run_local_voice_assistant())
    except KeyboardInterrupt:
        print("\nExiting voice assistant. Goodbye!")
