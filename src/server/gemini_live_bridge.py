import os
import json
import base64
import asyncio
import numpy as np
from typing import Optional
from loguru import logger
from google import genai
from google.genai import types

from src.server.audio_utils import decode_mulaw, encode_mulaw, resample_audio
from src.database.customer_repo import get_customer
from src.tools.booking_tools import execute_tool_call
from src.config import settings

GEMINI_TOOLS = [
    types.Tool(function_declarations=[
        {
            "name": "search_catalog",
            "description": "Search available grocery products and prices in DMart Express store catalog.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Grocery product name in Kannada, English, or Kanglish (e.g. milk, ಹಾಲು, sugar, ಸಕ್ಕರೆ, bread, ಬ್ರೆಡ್, rice, ಅಕ್ಕಿ, dal, ಬೇಳೆ)"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "check_stock",
            "description": "Check current stock availability and price for a product.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "product_name": {"type": "STRING", "description": "Product name to check"},
                    "quantity": {"type": "INTEGER", "description": "Quantity requested"}
                },
                "required": ["product_name"]
            }
        },
        {
            "name": "place_order",
            "description": "Place and confirm customer grocery order with automatic delivery.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "items": {
                        "type": "ARRAY",
                        "description": "List of items with exact name and quantity",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "name": {"type": "STRING"},
                                "quantity": {"type": "INTEGER"}
                            },
                            "required": ["name", "quantity"]
                        }
                    },
                    "delivery_type": {"type": "STRING", "enum": ["delivery", "pickup"]}
                },
                "required": ["items"]
            }
        },
        {
            "name": "register_caller",
            "description": "Register an unregistered caller's name and delivery address.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "customer_name": {"type": "STRING", "description": "Customer full name"},
                    "delivery_address": {"type": "STRING", "description": "Full street address in Bengaluru"}
                },
                "required": ["customer_name", "delivery_address"]
            }
        }
    ])
]

def build_gemini_instruction(caller_phone: str) -> str:
    cust = get_customer(caller_phone)
    store_name = settings.STORE_NAME
    if cust:
        return f"""You are 'Priya', the AI phone grocery assistant for {store_name} in Bengaluru, Karnataka.
You speak natural spoken Kannada (ಕನ್ನಡ) and English.

CALLER CONTEXT:
- Caller Name: {cust['name']}
- Registered Phone: {cust['phone_number']}
- Registered Delivery Address: {cust['address']}
- Status: REGISTERED CUSTOMER

STRICT OPERATING RULES:
1. GREETING: Welcome the customer warmly in Kannada using their name (e.g. "ನಮಸ್ಕಾರ {cust['name']}, {store_name} ಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು?").
2. DO NOT ASK FOR ADDRESS OR PHONE: Never ask for their phone number or delivery address because it is already registered ({cust['address']}).
3. GROCERY REQUESTS: When customer asks for items (like ಹಾಲು, ಬ್ರೆಡ್, ಸಕ್ಕರೆ, milk, bread, sugar, etc.), call `search_catalog` immediately to find matching products and mention prices.
4. ORDER CONFIRMATION: When the customer confirms, call `place_order`. Their registered address is automatically used.
5. FINAL SUMMARY IN KANNADA: After placing the order, clearly state the items, total rupees, delivery address ({cust['address']}), and expected arrival time (35-45 minutes).
6. VOICE STYLE: Speak in short, warm, natural conversational sentences (1-2 sentences at a time). No markdown, bullet points, or robotic speech."""
    else:
        return f"""You are 'Priya', the AI phone grocery assistant for {store_name} in Bengaluru, Karnataka.
You speak natural spoken Kannada (ಕನ್ನಡ) and English.

CALLER CONTEXT:
- Caller Phone: {caller_phone}
- Status: UNREGISTERED

STRICT OPERATING RULES:
1. GREETING & REGISTRATION: Welcome the caller in Kannada: "ನಮಸ್ಕಾರ! {store_name} ಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ ಮೊಬೈಲ್ ನಂಬರ್ ನೋಂದಣಿ ಆಗಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹೆಸರು ಮತ್ತು ವಿಳಾಸ ತಿಳಿಸುತ್ತೀರಾ?"
2. As soon as they provide name and address, call `register_caller`.
3. Then take their grocery order using `search_catalog` and `place_order`.
4. Keep spoken responses short and natural."""

def pcm24k_to_mulaw8k(pcm24k_bytes: bytes) -> bytes:
    """Converts 24kHz 16-bit linear PCM from Gemini into 8kHz G.711 mu-law for Twilio."""
    if not pcm24k_bytes:
        return b""
    pcm24k = np.frombuffer(pcm24k_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    pcm8k = resample_audio(pcm24k, orig_sr=24000, target_sr=8000)
    return encode_mulaw(pcm8k)

async def handle_gemini_live_session(websocket, stream_sid: str, caller_phone: str):
    """
    Pure Speech-to-Speech bi-directional bridge between Twilio and Gemini 2.5 Flash Native Audio.
    No local models, zero STT/TTS latency conflict, sub-500ms turnaround.
    """
    logger.info(f"[Gemini Live] Starting native speech session for {caller_phone} (SID: {stream_sid})")
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not configured!")
        return

    client = genai.Client(api_key=api_key)
    instruction = build_gemini_instruction(caller_phone)
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        thinking_config=types.ThinkingConfig(thinking_budget=0),  # Zero thinking delay for real-time speech
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
        system_instruction=types.Content(parts=[types.Part.from_text(text=instruction)]),
        tools=GEMINI_TOOLS
    )

    # Decoupled outbound queue for smooth Twilio streaming
    outbound_audio_queue = asyncio.Queue()
    is_session_active = True

    cust = get_customer(caller_phone)
    cust_name = cust['name'] if cust else "ಸರ್"

    is_greeting_playing = True

    async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
        logger.info(f"[Gemini Live] Connected! Triggering initial greeting in Gemini native voice...")
        
        # Trigger Gemini to speak welcome greeting natively in real-time mode
        welcome_prompt = f"Please speak the welcome greeting in natural spoken Kannada: 'ನಮಸ್ಕಾರ {cust_name}, D mart Express ಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು?'"
        await session.send_realtime_input(text=welcome_prompt)

        ws_lock = asyncio.Lock()

        async def send_ws(msg: dict):
            async with ws_lock:
                await websocket.send_text(json.dumps(msg))

        async def twilio_audio_sender():
            """Worker that drains the audio queue and streams 20ms chunks to Twilio smoothly."""
            chunks_sent = 0
            try:
                while is_session_active:
                    mulaw_chunk = await outbound_audio_queue.get()
                    if mulaw_chunk is None:
                        break
                    payload = base64.b64encode(mulaw_chunk).decode("utf-8")
                    msg = {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": payload}
                    }
                    await send_ws(msg)
                    chunks_sent += 1
                    await asyncio.sleep(0.018) # 20ms packet pacing
                    outbound_audio_queue.task_done()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[Twilio Sender] Worker error: {e}")
            finally:
                logger.info(f"[Twilio Sender] Finished. Total chunks sent to caller: {chunks_sent} ({chunks_sent * 0.02:.2f}s audio)")

        async def gemini_to_twilio():
            """Continuously receives audio and tool calls from Gemini Live across all conversational turns."""
            nonlocal is_session_active, is_greeting_playing
            try:
                while is_session_active:
                    async for response in session.receive():
                        sc = response.server_content
                        if sc is not None:
                            # Built-in acoustic barge-in from Gemini
                            if sc.interrupted:
                                logger.info("[Gemini Live] Caller interrupted / barge-in. Clearing Twilio buffer.")
                                while not outbound_audio_queue.empty():
                                    try:
                                        outbound_audio_queue.get_nowait()
                                        outbound_audio_queue.task_done()
                                    except Exception:
                                        break
                                await send_ws({"event": "clear", "streamSid": stream_sid})

                            model_turn = sc.model_turn
                            if model_turn is not None:
                                for part in model_turn.parts:
                                    if part.text:
                                        logger.info(f"Priya: {part.text}")
                                    if part.inline_data and part.inline_data.data:
                                        mulaw_bytes = pcm24k_to_mulaw8k(part.inline_data.data)
                                        chunk_size = 160
                                        for i in range(0, len(mulaw_bytes), chunk_size):
                                            chunk = mulaw_bytes[i:i + chunk_size]
                                            await outbound_audio_queue.put(chunk)

                            if sc.turn_complete:
                                if is_greeting_playing:
                                    is_greeting_playing = False
                                    logger.info("[Gemini Live] Welcome greeting finished generation. Now actively streaming and listening for caller orders!")
                                else:
                                    logger.info("[Gemini Live] Turn complete. Listening for caller response...")

                        # Handle Tool Calling (search catalog, place order, register)
                        if response.tool_call:
                            for call in response.tool_call.function_calls:
                                logger.info(f"[Tool Call] {call.name} args: {call.args}")
                                res = execute_tool_call(call.name, call.args, default_phone=caller_phone)
                                logger.info(f"[Tool Result] {res}")
                                if isinstance(res, str):
                                    try:
                                        res_dict = json.loads(res)
                                    except Exception:
                                        res_dict = {"result": res}
                                elif isinstance(res, dict):
                                    res_dict = res
                                else:
                                    res_dict = {"result": str(res)}

                                await session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(
                                            name=call.name,
                                            id=call.id,
                                            response=res_dict
                                        )
                                    ]
                                )
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[Gemini-to-Twilio] Loop error: {e}", exc_info=True)
            finally:
                logger.info("[Gemini-to-Twilio] Task ended.")
                is_session_active = False

        async def twilio_to_gemini():
            """Batches incoming Twilio audio (100ms chunks) and sends to Gemini via media= Blob."""
            nonlocal is_session_active, is_greeting_playing
            buffer_16k = []
            frames_forwarded = 0
            try:
                while is_session_active:
                    raw_msg = await websocket.receive_text()
                    data = json.loads(raw_msg)
                    event_type = data.get("event")

                    if event_type == "media":
                        payload = data["media"]["payload"]
                        mulaw_bytes = base64.b64decode(payload)
                        # Decode 8k mu-law -> float32 -> resample to 16k
                        audio_8k = decode_mulaw(mulaw_bytes)
                        audio_16k = resample_audio(audio_8k, orig_sr=8000, target_sr=16000)
                        buffer_16k.append(audio_16k)

                        # Send every 5 frames (~100ms) as mediaChunks to Gemini Live
                        if len(buffer_16k) >= 5:
                            combined = np.concatenate(buffer_16k)
                            buffer_16k.clear()
                            pcm16 = (np.clip(combined, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
                            await session.send_realtime_input(
                                media=types.Blob(data=pcm16, mime_type="audio/pcm;rate=16000")
                            )
                            frames_forwarded += 1
                            if frames_forwarded % 10 == 0:
                                logger.info(f"[Twilio->Gemini] Forwarded {frames_forwarded * 0.1:.1f}s of caller speech")

                    elif event_type == "stop":
                        logger.info(f"[Twilio] Caller hung up (stop event received for SID {stream_sid})")
                        break
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[Twilio-to-Gemini] Loop error: {e}", exc_info=True)
            finally:
                logger.info(f"[Twilio-to-Gemini] Task ended (total audio forwarded: {frames_forwarded * 0.1:.1f}s).")
                is_session_active = False

        # Run sender worker and both directions concurrently
        worker_task = asyncio.create_task(twilio_audio_sender())
        gemini_task = asyncio.create_task(gemini_to_twilio())
        twilio_task = asyncio.create_task(twilio_to_gemini())

        done, pending = await asyncio.wait(
            [gemini_task, twilio_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        for t in done:
            if t == gemini_task:
                logger.info("[Session] gemini_task finished first.")
            elif t == twilio_task:
                logger.info("[Session] twilio_task finished first.")
            exc = t.exception()
            if exc:
                logger.error(f"[Session] Completed task had error: {exc}", exc_info=True)

        is_session_active = False
        await outbound_audio_queue.put(None)
        worker_task.cancel()
        for p in pending:
            p.cancel()

        logger.info(f"[Gemini Live] Session cleanly finished for {caller_phone}.")
