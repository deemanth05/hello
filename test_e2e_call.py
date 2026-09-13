import asyncio
import json
import base64
import time
import io
import wave
import websockets
import numpy as np
from src.services.tts_service import TTSService
from src.server.audio_utils import wav_bytes_to_mulaw8k

import sys

async def run_e2e_test(target_url: str = None):
    if not target_url:
        target_url = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765/voice/stream"
    print(f"============================================================")
    print(f"Starting End-to-End Voice Telephony Test against:")
    print(f"  {target_url}")
    print(f"============================================================")

    # Pre-synthesize caller speech using TTS
    tts = TTSService()
    order_speech = "I want two liters of milk and one packet of bread"
    print(f"[Caller Simulator] Synthesizing speech: '{order_speech}'...")
    wav_bytes = tts.synthesize_wav_bytes(order_speech)
    mulaw_caller_audio = wav_bytes_to_mulaw8k(wav_bytes)
    print(f"[Caller Simulator] Synthesized {len(mulaw_caller_audio)} bytes of 8kHz mu-law audio (~{len(mulaw_caller_audio)/8000:.2f}s).")

    stream_sid = "E2E_SIMULATED_CALL_001"
    caller_phone = sys.argv[2] if len(sys.argv) > 2 else "+919008474173"

    print(f"\n[E2E] Connecting to WebSocket {target_url} for caller {caller_phone}...")
    async with websockets.connect(target_url) as ws:
        print("[E2E] Connected! Sending Twilio 'start' event...")
        start_msg = {
            "event": "start",
            "streamSid": stream_sid,
            "start": {
                "streamSid": stream_sid,
                "customParameters": {
                    "caller": caller_phone
                }
            }
        }
        await ws.send(json.dumps(start_msg))

        # ------------------------------------------------------------
        # STEP 1: Listen for Priya's initial greeting
        # ------------------------------------------------------------
        print("\n--- STEP 1: Receiving Initial Greeting from Priya ---", flush=True)
        greeting_chunks = 0
        greeting_bytes = 0
        greeting_start_time = None

        while True:
            try:
                # Wait up to 15.0s for first packet from cloud, but only 1.8s between packets once started
                wait_sec = 15.0 if greeting_chunks == 0 else 1.8
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=wait_sec)
                msg = json.loads(msg_raw)
                if msg.get("event") == "media":
                    if greeting_start_time is None:
                        greeting_start_time = time.time()
                        print(f"[Priya Audio] First greeting packet arrived! (TTFB: {time.time() - greeting_start_time:.2f}s)", flush=True)
                    
                    payload = base64.b64decode(msg["media"]["payload"])
                    greeting_chunks += 1
                    greeting_bytes += len(payload)
                elif msg.get("event") == "clear":
                    print("[Priya] Clear event received.", flush=True)
            except asyncio.TimeoutError:
                if greeting_chunks > 0:
                    print(f"[Priya Audio] Greeting finished! Total {greeting_chunks} chunks ({greeting_bytes} bytes, ~{greeting_bytes/8000:.2f}s audio).", flush=True)
                    break
                else:
                    print("[FAIL] Timeout waiting for first greeting packet!", flush=True)
                    return False

        if greeting_chunks == 0:
            print("[FAIL] Never received greeting audio from Priya!")
            return False

        print(f"[SUCCESS] Greeting received cleanly: {greeting_chunks} packets, ~{greeting_bytes/8000:.2f}s.")

        # Brief pause to simulate human comprehension (500ms)
        await asyncio.sleep(0.5)

        # ------------------------------------------------------------
        # STEP 2: Caller speaks grocery order
        # ------------------------------------------------------------
        print(f"\n--- STEP 2: Caller speaks: '{order_speech}' ---", flush=True)
        chunk_size = 160 # 20ms at 8kHz mu-law
        speech_start_time = time.time()
        
        for i in range(0, len(mulaw_caller_audio), chunk_size):
            chunk = mulaw_caller_audio[i:i + chunk_size]
            payload = base64.b64encode(chunk).decode("utf-8")
            media_msg = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload}
            }
            await ws.send(json.dumps(media_msg))
            await asyncio.sleep(0.018) # 20ms pacing

        # Send 1.2s of telephone ambient silence (mu-law 0xFF is quiet silence) so VAD detects turn end
        print("[Caller Simulator] Finished speaking. Sending silence for VAD trigger...", flush=True)
        silence_chunk = b'\xff' * 160
        for _ in range(60): # 60 * 20ms = 1.2s
            payload = base64.b64encode(silence_chunk).decode("utf-8")
            media_msg = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {"payload": payload}
            }
            await ws.send(json.dumps(media_msg))
            await asyncio.sleep(0.018)

        # ------------------------------------------------------------
        # STEP 3: Listen for Priya's response to the order
        # ------------------------------------------------------------
        print("\n--- STEP 3: Waiting for Priya's response to order ---", flush=True)
        order_response_chunks = 0
        order_response_bytes = 0
        order_resp_start = None
        
        start_wait = time.time()
        while True:
            try:
                wait_time = 15.0 if order_response_chunks == 0 else 1.5
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=wait_time)
                msg = json.loads(msg_raw)
                if msg.get("event") == "media":
                    if order_resp_start is None:
                        order_resp_start = time.time()
                        latency = order_resp_start - (speech_start_time + len(mulaw_caller_audio)/8000)
                        print(f"[Priya Audio] Response arrived! Latency from speech end: {latency:.2f}s", flush=True)
                    
                    payload = base64.b64decode(msg["media"]["payload"])
                    order_response_chunks += 1
                    order_response_bytes += len(payload)
                elif msg.get("event") == "clear":
                    print("[Priya] Clear buffer event.", flush=True)
            except asyncio.TimeoutError:
                if order_response_chunks > 0:
                    print(f"[Priya Audio] Turn 2 response completed! Total {order_response_chunks} chunks ({order_response_bytes} bytes, ~{order_response_bytes/8000:.2f}s audio).", flush=True)
                    break
                else:
                    elapsed = time.time() - start_wait
                    if elapsed > 15:
                        print(f"[FAIL] Priya did not respond within 15 seconds!", flush=True)
                        return False
                    print(f"[Waiting] Still waiting for Priya ({elapsed:.1f}s elapsed)...", flush=True)

        if order_response_chunks > 0:
            print("\n============================================================", flush=True)
            print("END-TO-END TEST PASSED SUCCESSFULLY!", flush=True)
            print(f"1. Greeting Audio: {greeting_bytes} bytes (~{greeting_bytes/8000:.2f}s)", flush=True)
            print(f"2. Caller Speech Streamed: {len(mulaw_caller_audio)} bytes (~{len(mulaw_caller_audio)/8000:.2f}s)", flush=True)
            print(f"3. Priya Order Response: {order_response_bytes} bytes (~{order_response_bytes/8000:.2f}s)", flush=True)
            print("============================================================", flush=True)
            
            # Send stop event
            await ws.send(json.dumps({"event": "stop", "streamSid": stream_sid}))
            return True
        else:
            print("\n[FAIL] Priya failed to respond to the caller's order!", flush=True)
            return False

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
