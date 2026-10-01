import os
import json
import base64
import asyncio
import time
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
                        "description": "Complete cumulative list of ALL items and quantities requested by the customer across the entire call. DO NOT skip or omit earlier items.",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "name": {"type": "STRING", "description": "Product name (e.g. milk, ಹಾಲು, sugar, ಸಕ್ಕರೆ, bread, ಬ್ರೆಡ್, tea, coffee)"},
                                "quantity": {"type": "INTEGER", "description": "Quantity requested"}
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
    from src.database.settings_repo import get_setting
    store_name = get_setting("store_name", settings.STORE_NAME)
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
3. GROCERY REQUESTS & CUMULATIVE CART:
   - When customer asks for items (like ಹಾಲು, ಬ್ರೆಡ್, ಸಕ್ಕರೆ, milk, bread, sugar, etc.), call `search_catalog` immediately to find matching products and mention prices.
   - Only recommend varieties of the exact requested product (e.g. Amul Taaza 1L for ₹54 or Amul Gold 1L for ₹68). NEVER suggest unrelated items (such as eggs or other categories) unless the customer explicitly asked for them.
   - CUMULATIVE CART RETENTION: Maintain a strict cumulative cart of ALL items requested across the entire conversation. If customer asks for milk in turn 1, and later asks for bread and sugar in turn 2, your cart MUST retain ALL THREE items. NEVER drop or forget earlier items!
4. ORDER CONFIRMATION & CART RECAP:
   - When the customer asks to place or confirm the order, recap the full list of items in the cart in Kannada to verify with the customer.
   - When confirmed, IMMEDIATELY call `place_order` with the complete list of ALL requested items in the `items` array. Every single item mentioned across the conversation must be present with its correct quantity.
5. FINAL SPOKEN SUMMARY IN KANNADA: After calling `place_order`, speak the complete order confirmation warmly in Kannada: announce the Order ID, items ordered, total amount in rupees, delivery address ({cust['address']}), and expected delivery arrival time (e.g. 35 ರಿಂದ 40 ನಿಮಿಷಗಳಲ್ಲಿ). Conclude with a polite thank you ("ಧನ್ಯವಾದಗಳು!").
6. VOICE STYLE: Speak in short, warm, natural conversational Kannada sentences. No markdown, bullet points, or robotic speech."""
    else:
        return f"""You are 'Priya', the AI phone grocery assistant for {store_name} in Bengaluru, Karnataka.
You speak natural spoken Kannada (ಕನ್ನಡ) and English.

CALLER CONTEXT:
- Caller Phone: {caller_phone}
- Status: UNREGISTERED

STRICT OPERATING RULES:
1. GREETING & REGISTRATION: Welcome the caller in Kannada: "ನಮಸ್ಕಾರ! {store_name} ಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ ಮೊಬೈಲ್ ನಂಬರ್ ನೋಂದಣಿ ಆಗಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹೆಸರು ಮತ್ತು ವಿಳಾಸ ತಿಳಿಸುತ್ತೀರಾ?"
2. When the caller provides their name and delivery address, IMMEDIATELY call `register_caller(customer_name=..., delivery_address=...)`.
3. GROCERY REQUESTS & CUMULATIVE CART: Help them choose items using `search_catalog`. Suggest only varieties of what they requested; NEVER suggest unrelated items like eggs unless asked. Maintain a cumulative cart across all turns so no requested item is dropped.
4. ORDER CONFIRMATION: Recap the full list of items in the cart, and when the customer confirms, IMMEDIATELY call `place_order` with all requested items.
5. FINAL SPOKEN SUMMARY IN KANNADA: After calling `place_order`, speak the complete order confirmation warmly in Kannada: announce the Order ID, items ordered, total amount in rupees, their delivery address, and expected delivery arrival time (35 ರಿಂದ 40 ನಿಮಿಷಗಳಲ್ಲಿ). Conclude with "ಧನ್ಯವಾದಗಳು!".
6. VOICE STYLE: Speak in short, warm, natural conversational Kannada sentences."""

def pcm24k_to_mulaw8k(pcm24k_bytes: bytes) -> bytes:
    """Converts 24kHz 16-bit linear PCM from Gemini into 8kHz G.711 mu-law for Twilio with anti-aliasing."""
    if not pcm24k_bytes:
        return b""
    pcm16 = np.frombuffer(pcm24k_bytes, dtype=np.int16)
    # Boxcar anti-aliased 3:1 integer decimation (24,000 Hz -> 8,000 Hz)
    remainder = len(pcm16) % 3
    if remainder:
        pcm16 = pcm16[:-remainder]
    if len(pcm16) == 0:
        return b""
    downsampled_float = pcm16.reshape(-1, 3).mean(axis=1).astype(np.float32) / 32768.0
    return encode_mulaw(downsampled_float)

async def handle_gemini_live_session(websocket, stream_sid: str, caller_phone: str):
    """
    Pure Speech-to-Speech bi-directional bridge between Twilio and Gemini 2.5 Flash Native Audio.
    No local models, zero STT/TTS latency conflict, sub-500ms turnaround, jitter-compensated streaming.
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
    is_model_generating = False
    is_resolving_tool = False
    is_waiting_for_model_turn = True
    is_order_placed = False
    last_audio_sent_time = 0.0
    last_loud_speech_time = 0.0
    stream_start_time = time.perf_counter()

    def is_bot_active() -> bool:
        """Returns True if Gemini is generating, queue has pending audio, or speaker echo is still dissipating."""
        if is_model_generating or is_resolving_tool or is_waiting_for_model_turn:
            return True
        if not outbound_audio_queue.empty():
            return True
        # Keep active for 800ms after last chunk was sent to Twilio for acoustic dissipation & network jitter
        if (time.perf_counter() - last_audio_sent_time) < 0.800:
            return True
        return False

    cust = get_customer(caller_phone)
    cust_name = cust['name'] if cust else "ಸರ್"
    from src.database.settings_repo import get_setting
    from src.database.call_log_repo import log_call_start, log_call_end
    store_name = get_setting("store_name", settings.STORE_NAME)
    created_order_id = None
    log_call_start(call_sid=call_sid or stream_sid, caller_phone=caller_phone, customer_name=cust['name'] if cust else "Caller")

    is_greeting_playing = True

    async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
        logger.info(f"[Gemini Live] Connected! Triggering initial greeting in Gemini native voice...")
        
        # Trigger Gemini to speak welcome greeting natively in real-time mode
        if cust:
            welcome_prompt = f"Please speak the welcome greeting in natural spoken Kannada: 'ನಮಸ್ಕಾರ {cust_name}, {store_name} ಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು?'"
        else:
            welcome_prompt = f"Please speak the welcome greeting in natural spoken Kannada asking for registration: 'ನಮಸ್ಕಾರ! {store_name} ಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ ಮೊಬೈಲ್ ನಂಬರ್ ನೋಂದಣಿ ಆಗಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹೆಸರು ಮತ್ತು ವಿಳಾಸ ತಿಳಿಸುತ್ತೀರಾ?'"
        await session.send_realtime_input(text=welcome_prompt)

        ws_lock = asyncio.Lock()

        async def send_ws(msg: dict):
            async with ws_lock:
                await websocket.send_text(json.dumps(msg))

        turn_chunks_sent = 0

        async def twilio_audio_sender():
            """Worker that drains the audio queue with drift-compensated 40ms timing and initial buffer priming."""
            nonlocal last_audio_sent_time, turn_chunks_sent
            chunks_sent = 0
            next_send_time = time.perf_counter()
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
                    turn_chunks_sent += 1
                    last_audio_sent_time = time.perf_counter()
                    
                    chunk_duration = len(mulaw_chunk) / 8000.0
                    now = time.perf_counter()

                    # Prime Twilio's jitter buffer with first 3 chunks (120ms) instantly to prevent buffer underflow
                    if turn_chunks_sent <= 3:
                        next_send_time = now
                    else:
                        if next_send_time < now - 0.1:
                            next_send_time = now
                        next_send_time += chunk_duration
                        sleep_dur = next_send_time - time.perf_counter()
                        if sleep_dur > 0.002:
                            await asyncio.sleep(sleep_dur)
                    
                    outbound_audio_queue.task_done()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[Twilio Sender] Worker error: {e}")
            finally:
                logger.info(f"[Twilio Sender] Finished. Total chunks sent to caller: {chunks_sent}")

        async def gemini_to_twilio():
            """Continuously receives audio and tool calls from Gemini Live across all conversational turns."""
            nonlocal is_session_active, is_greeting_playing, is_model_generating, is_resolving_tool, is_waiting_for_model_turn, is_order_placed, turn_chunks_sent
            try:
                while is_session_active:
                    async for response in session.receive():
                        sc = response.server_content
                        if sc is not None:
                            # Built-in acoustic barge-in from Gemini
                            if sc.interrupted:
                                if is_order_placed:
                                    logger.info("[Gemini Live] Order confirmation active: ignoring barge-in to guarantee full confirmation playback.")
                                else:
                                    now = time.perf_counter()
                                    if (now - last_loud_speech_time) <= 0.8:
                                        logger.info(f"[Gemini Live] Legitimate caller barge-in detected. Clearing queue ({outbound_audio_queue.qsize()} chunks).")
                                        while not outbound_audio_queue.empty():
                                            try:
                                                outbound_audio_queue.get_nowait()
                                                outbound_audio_queue.task_done()
                                            except Exception:
                                                break
                                        await send_ws({"event": "clear", "streamSid": stream_sid})
                                        is_model_generating = False
                                        turn_chunks_sent = 0
                                    else:
                                        logger.info("[Gemini Live] Dropping false barge-in trigger (no recent loud caller speech). Keeping audio queue intact.")

                            model_turn = sc.model_turn
                            if model_turn is not None:
                                is_waiting_for_model_turn = False
                                for part in model_turn.parts:
                                    if part.text:
                                        logger.info(f"Priya: {part.text}")
                                    if part.inline_data and part.inline_data.data:
                                        is_model_generating = True
                                        mulaw_bytes = pcm24k_to_mulaw8k(part.inline_data.data)
                                        # Use 40ms chunks (320 bytes at 8kHz mu-law) for smooth streaming
                                        chunk_size = 320
                                        for i in range(0, len(mulaw_bytes), chunk_size):
                                            chunk = mulaw_bytes[i:i + chunk_size]
                                            await outbound_audio_queue.put(chunk)

                            if sc.turn_complete:
                                is_model_generating = False
                                is_waiting_for_model_turn = False
                                turn_chunks_sent = 0
                                if is_greeting_playing:
                                    is_greeting_playing = False
                                    logger.info("[Gemini Live] Welcome greeting finished generation. Now actively streaming and listening for caller orders!")
                                else:
                                    logger.info("[Gemini Live] Turn complete. Listening for caller response...")

                        # Handle Tool Calling (search catalog, place order, register)
                        if response.tool_call:
                            is_resolving_tool = True
                            is_waiting_for_model_turn = True
                            try:
                                function_responses = []
                                for call in response.tool_call.function_calls:
                                    logger.info(f"[Tool Call] {call.name} args: {call.args}")
                                    if call.name == "place_order":
                                        is_order_placed = True
                                    res = execute_tool_call(call.name, call.args, default_phone=caller_phone)
                                    logger.info(f"[Tool Result] {res}")
                                    if call.name == "place_order":
                                        if isinstance(res, dict) and res.get("order_id"):
                                            created_order_id = res["order_id"]
                                        elif isinstance(res, str):
                                            try:
                                                r_json = json.loads(res)
                                                if r_json.get("order_id"):
                                                    created_order_id = r_json["order_id"]
                                            except Exception:
                                                pass
                                    if isinstance(res, str):
                                        try:
                                            res_dict = json.loads(res)
                                        except Exception:
                                            res_dict = {"result": res}
                                    elif isinstance(res, dict):
                                        res_dict = res
                                    else:
                                        res_dict = {"result": str(res)}

                                    function_responses.append(
                                        types.FunctionResponse(
                                            name=call.name,
                                            id=call.id,
                                            response=res_dict
                                        )
                                    )

                                if function_responses:
                                    await session.send_tool_response(function_responses=function_responses)
                                    logger.info(f"[Gemini Live] Sent {len(function_responses)} tool responses to Gemini session.")
                            except Exception as tool_err:
                                logger.error(f"[Gemini Live] Tool execution error: {tool_err}", exc_info=True)
                            finally:
                                is_resolving_tool = False
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[Gemini-to-Twilio] Loop error: {e}", exc_info=True)
            finally:
                logger.info("[Gemini-to-Twilio] Task ended.")
                is_session_active = False

        async def twilio_to_gemini():
            """Batches incoming Twilio audio (100ms chunks) and sends to Gemini via media= Blob with robust echo suppression."""
            nonlocal is_session_active, is_greeting_playing, last_loud_speech_time
            buffer_16k = []
            frames_forwarded = 0
            frames_suppressed = 0
            try:
                while is_session_active:
                    raw_msg = await websocket.receive_text()
                    data = json.loads(raw_msg)
                    event_type = data.get("event")

                    if event_type == "media":
                        # Discard first 1.0s to avoid DTMF trial remnants
                        now = time.perf_counter()
                        if (now - stream_start_time) < 1.0:
                            continue

                        # Gate incoming audio while tool calls are resolving or waiting for model turn
                        if is_resolving_tool or is_waiting_for_model_turn:
                            continue

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

                            # If bot is active (generating speech, playing audio to caller, or speaker sound still echoing):
                            # Suppress microphone sound so Gemini Live never hears its own voice.
                            # Only allow intentional, loud human barge-in (RMS >= 0.18)
                            rms = float(np.sqrt(np.mean(combined ** 2)))
                            if is_bot_active():
                                if is_order_placed or rms < 0.18:
                                    frames_suppressed += 1
                                    continue
                                else:
                                    last_loud_speech_time = time.perf_counter()
                                    logger.info(f"[Echo Gate] Loud user speech detected during bot playback (RMS: {rms:.4f})")
                            else:
                                if rms >= 0.18:
                                    last_loud_speech_time = time.perf_counter()

                            pcm16 = (np.clip(combined, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
                            await session.send_realtime_input(
                                media=types.Blob(data=pcm16, mime_type="audio/pcm;rate=16000")
                            )
                            frames_forwarded += 1
                            if frames_forwarded % 20 == 0:
                                logger.info(f"[Twilio->Gemini] Forwarded {frames_forwarded * 0.1:.1f}s speech (Echo suppressed: {frames_suppressed * 0.1:.1f}s)")

                    elif event_type == "stop":
                        logger.info(f"[Twilio] Caller hung up (stop event received for SID {stream_sid})")
                        break
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[Twilio-to-Gemini] Loop error: {e}", exc_info=True)
            finally:
                logger.info(f"[Twilio-to-Gemini] Task ended (total audio forwarded: {frames_forwarded * 0.1:.1f}s, echo suppressed: {frames_suppressed * 0.1:.1f}s).")
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

        # Allow remaining audio in queue to finish playing to caller before tearing down
        if not outbound_audio_queue.empty():
            logger.info(f"[Session] Draining {outbound_audio_queue.qsize()} pending audio chunks before closing...")
            drain_deadline = time.perf_counter() + 3.0
            while not outbound_audio_queue.empty() and time.perf_counter() < drain_deadline:
                await asyncio.sleep(0.05)

        is_session_active = False
        await outbound_audio_queue.put(None)
        worker_task.cancel()
        for p in pending:
            p.cancel()

        logger.info(f"[Gemini Live] Session cleanly finished for {caller_phone}.")
        try:
            duration = int(time.perf_counter() - stream_start_time)
            log_call_end(
                call_sid=call_sid or stream_sid,
                status="COMPLETED",
                duration_seconds=duration,
                order_id=created_order_id,
                summary=f"Order {created_order_id} placed" if created_order_id else "Call completed"
            )
        except Exception as log_err:
            logger.error(f"Error logging call end: {log_err}")
