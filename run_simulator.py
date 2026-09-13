import sys
import os
import asyncio
import numpy as np
import io
import wave
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.config import settings
from src.database.db import init_db
from src.database.customer_repo import get_customer, list_all_customers, register_customer
from src.database.booking_repo import list_all_customers as _, search_products
from src.pipeline.bot_pipeline import VoiceBotPipeline

def play_audio_bytes(wav_bytes: bytes):
    """Plays WAV audio bytes through speakers using sounddevice."""
    try:
        import sounddevice as sd
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            audio_out = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            if n_channels > 1:
                audio_out = audio_out.reshape(-1, n_channels)
            sd.play(audio_out, samplerate=sr)
            sd.wait()
    except Exception as e:
        print(f"(Audio playback notice: {e})")

async def run_text_mode(caller_phone: str):
    """Interactive text chat simulation with TTS voice playback."""
    print("\n" + "="*65)
    print(f"DMart Express Voice AI Simulator - Text Mode")
    print(f"Caller Phone Number: {caller_phone}")
    cust = get_customer(caller_phone)
    if cust:
        print(f"Caller Status: REGISTERED -> {cust['name']} ({cust['address']})")
    else:
        print(f"Caller Status: UNREGISTERED (Will trigger voice registration)")
    print("Type 'exit' or 'quit' to end the call.")
    print("="*65 + "\n")
    
    pipeline = VoiceBotPipeline(caller_phone=caller_phone)
    greeting_text, greeting_wav = pipeline.set_caller(caller_phone)
    
    print(f"Priya (AI): {greeting_text}\n")
    play_audio_bytes(greeting_wav)
    
    loop = asyncio.get_running_loop()
    while True:
        try:
            user_input = await loop.run_in_executor(None, input, "You (Caller): ")
            user_input = user_input.strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "bye", "hangup"]:
                print("\n[Call Ended. Thank you for calling DMart Express!]\n")
                break
                
            turn_res = await pipeline.execute_text_turn(user_input)
            print(f"\nPriya (AI): {turn_res['reply_text']}\n")
            if turn_res.get("wav_bytes"):
                play_audio_bytes(turn_res["wav_bytes"])
                
        except (KeyboardInterrupt, EOFError):
            print("\n[Call Ended.]")
            break

async def run_mic_mode(caller_phone: str):
    """Interactive live microphone voice simulation."""
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice library is required for mic mode. Please install requirements.")
        return
        
    print("\n" + "="*65)
    print(f"DMart Express Voice AI Simulator - Live Microphone Mode")
    print(f"Caller Phone: {caller_phone}")
    cust = get_customer(caller_phone)
    if cust:
        print(f"Caller Status: REGISTERED -> {cust['name']} ({cust['address']})")
    else:
        print(f"Caller Status: UNREGISTERED (In-call voice registration)")
    print("Speak naturally into your microphone. Press Ctrl+C to hang up.")
    print("="*65 + "\n")
    
    pipeline = VoiceBotPipeline(caller_phone=caller_phone)
    greeting_text, greeting_wav = pipeline.set_caller(caller_phone)
    
    print(f"Priya (AI): {greeting_text}\n")
    play_audio_bytes(greeting_wav)
    
    chunk_size = 1600 # 100ms at 16kHz
    sample_rate = 16000
    loop = asyncio.get_running_loop()
    audio_queue = asyncio.Queue()

    def mic_callback(indata, frames, time, status):
        loop.call_soon_threadsafe(audio_queue.put_nowait, indata[:, 0].copy())

    print("Listening... (Speak when ready)")
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='float32', blocksize=chunk_size, callback=mic_callback):
        while True:
            chunk = await audio_queue.get()
            speech_segment = pipeline.process_audio_chunk(chunk)
            
            if speech_segment is not None:
                print("\n[VAD]: User finished speaking. Processing turn...")
                turn_res = await pipeline.execute_turn(speech_segment)
                if turn_res:
                    print(f"Caller Said: \"{turn_res['transcript']}\"")
                    print(f"Priya (AI):  \"{turn_res['reply_text']}\"\n")
                    if turn_res.get("wav_bytes"):
                        play_audio_bytes(turn_res["wav_bytes"])
                print("Listening again...")

def print_menu():
    print("\n" + "="*60)
    print("      DMART EXPRESS LOCAL VOICE AI SYSTEM (ಕನ್ನಡ & English)")
    print("="*60)
    print("Select Caller Profile to Test:")
    print(" [1] Registered Customer: Rahul Sharma (+919876543210, Mumbai)")
    print(" [2] Registered Customer: Priya Patel  (+919812345678, Bangalore)")
    print(" [3] Unregistered Caller: New Customer (+919111222333)")
    print(" [4] Enter Custom Phone Number")
    print(" [5] Run Automated Kannada Tests (ಕನ್ನಡ - gemma3:latest)")
    print(" [6] Run Automated English Tests (qwen2.5:7b)")
    print(" [7] View Registered Customers & Supermarket Catalog")
    print(" [0] Exit")
    print("="*60)

async def main():
    init_db()
    
    while True:
        print_menu()
        choice = input("Enter choice (0-7): ").strip()
        
        if choice == "0":
            print("Exiting simulator. Goodbye / ಧನ್ಯವಾದಗಳು!")
            break
            
        elif choice == "1":
            phone = "+919876543210"
        elif choice == "2":
            phone = "+919812345678"
        elif choice == "3":
            phone = "+919111222333"
        elif choice == "4":
            phone = input("Enter caller phone number (e.g. +919876543210): ").strip()
            if not phone:
                phone = "+919876543210"
        elif choice == "5":
            from tests.test_kannada_flow import main as run_kannada_test_flow
            await run_kannada_test_flow()
            continue
        elif choice == "6":
            from tests.test_customer_flow import main as run_english_test_flow
            await run_english_test_flow()
            continue
        elif choice == "7":
            customers = list_all_customers()
            print(f"\n--- Registered Customers ({len(customers)}) ---")
            for c in customers[:6]:
                print(f" - {c['name']} ({c['phone_number']}): {c['address']}")
            products = search_products("")
            print(f"\n--- Sample Supermarket Catalog ({len(products)} items) ---")
            for p in products[:8]:
                print(f" - {p['name']} ({p['category']}) - Rs. {p['price']} ({p['unit']})")
            continue
        else:
            print("Invalid choice, please select 0-7.")
            continue
            
        print("\nSelect Interaction Mode:")
        print(" [1] Text Chat Mode (Fast text input + Voice TTS playback)")
        print(" [2] Live Microphone Mode (Real speech audio input + Voice TTS)")
        mode = input("Enter mode (1 or 2, default 1): ").strip()
        
        if mode == "2":
            try:
                await run_mic_mode(phone)
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
        else:
            await run_text_mode(phone)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
