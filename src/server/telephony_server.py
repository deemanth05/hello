import json
import base64
import asyncio
import numpy as np
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from pathlib import Path
from src.config import settings, BASE_DIR
from src.database.db import init_db
from src.database.customer_repo import get_customer, list_all_customers, register_customer
from src.database.booking_repo import search_products, get_order_details, list_recent_orders
from src.server.audio_utils import decode_mulaw, resample_audio, wav_bytes_to_mulaw8k

app = FastAPI(title="DMart Express Voice AI Telephony Server", version="2.0.0")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
sim_sessions = {}

# Shared pipeline instances (lazily initialized only for local mode)
bot_pipeline = None

@app.on_event("startup")
async def startup_event():
    global bot_pipeline
    logger.info("Initializing Database...")
    init_db()
    if not settings.GEMINI_API_KEY:
        logger.info("No GEMINI_API_KEY detected. Pre-loading local Voice AI models (Faster-Whisper, Piper TTS, Ollama)...")
        from src.pipeline.bot_pipeline import VoiceBotPipeline
        bot_pipeline = VoiceBotPipeline()
    else:
        logger.info("Gemini 2.5 Multimodal Live Speech-to-Speech engine active. Cloud-native mode ready!")
    logger.info("Voice AI Telephony Server ready!")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>DMart Express Voice AI Server Active</h1><p>Visit <a href='/health'>/health</a></p>")

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "store": settings.STORE_NAME,
        "model": "gemini-2.5-flash-native-audio-latest" if settings.GEMINI_API_KEY else settings.OLLAMA_MODEL
    }

@app.get("/api/customers")
async def api_customers():
    return {"customers": list_all_customers()}

@app.get("/api/products")
async def api_products(query: str = ""):
    return {"products": search_products(query)}

@app.get("/api/orders")
async def api_list_orders():
    return {"orders": list_recent_orders()}

@app.get("/api/orders/{order_id}")
async def api_order(order_id: str):
    return get_order_details(order_id)

@app.post("/api/register")
async def api_register(data: dict):
    phone = data.get("phone", "")
    name = data.get("name", "")
    address = data.get("address", "")
    res = register_customer(phone_number=phone, name=name, address=address)
    return res

@app.post("/api/simulate/call")
async def api_simulate_call(data: dict):
    from src.pipeline.bot_pipeline import VoiceBotPipeline
    phone = data.get("caller_phone", "+919876543210")
    pipeline = VoiceBotPipeline(
        caller_phone=phone,
        stt_service=bot_pipeline.stt if bot_pipeline else None,
        llm_service=bot_pipeline.llm if bot_pipeline else None,
        tts_service=bot_pipeline.tts if bot_pipeline else None
    )
    sim_sessions[phone] = pipeline
    greeting_text, greeting_wav = pipeline.set_caller(phone)
    cust = get_customer(phone)
    return {
        "caller_phone": phone,
        "customer": cust,
        "greeting_text": greeting_text,
        "audio_base64": base64.b64encode(greeting_wav).decode("utf-8") if greeting_wav else None
    }

@app.post("/api/simulate/turn")
async def api_simulate_turn(data: dict):
    phone = data.get("caller_phone", "+919876543210")
    user_text = data.get("text", "")
    pipeline = sim_sessions.get(phone)
    if not pipeline:
        from src.pipeline.bot_pipeline import VoiceBotPipeline
        pipeline = VoiceBotPipeline(
            caller_phone=phone,
            stt_service=bot_pipeline.stt if bot_pipeline else None,
            llm_service=bot_pipeline.llm if bot_pipeline else None,
            tts_service=bot_pipeline.tts if bot_pipeline else None
        )
        sim_sessions[phone] = pipeline
        pipeline.set_caller(phone)
    
    turn_res = await pipeline.execute_text_turn(user_text)
    wav_b64 = base64.b64encode(turn_res["wav_bytes"]).decode("utf-8") if turn_res.get("wav_bytes") else None
    return {
        "transcript": turn_res["transcript"],
        "reply_text": turn_res["reply_text"],
        "audio_base64": wav_b64
    }


@app.api_route("/voice/incoming", methods=["GET", "POST"])
async def voice_incoming(request: Request):
    """
    Twilio Voice webhook for incoming calls.
    Returns TwiML that connects the call audio to our WebSocket stream.
    """
    form_data = await request.form() if request.method == "POST" else request.query_params
    caller = form_data.get("From", "+919876543210")
    call_sid = form_data.get("CallSid", "")
    
    host = request.headers.get("host", f"localhost:{settings.SERVER_PORT}")
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    is_secure = (
        forwarded_proto == "https"
        or "https" in str(request.url)
        or "ngrok" in host
        or "cloudflare" in host
        or "onrender.com" in host
        or not ("localhost" in host or "127.0.0.1" in host)
    )
    ws_protocol = "wss" if is_secure else "ws"
    stream_url = f"{ws_protocol}://{host}/voice/stream"
    
    logger.info(f"Incoming call {call_sid} from {caller}. Connecting to stream: {stream_url}")
    
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="caller" value="{caller}" />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml_response, media_type="text/xml")

@app.websocket("/voice/stream")
async def voice_stream_endpoint(websocket: WebSocket):
    """
    Bi-directional Twilio Media Stream WebSocket:
    1. Receives 8kHz G.711 mu-law audio chunks from caller.
    2. Runs real-time VAD, local Faster-Whisper STT, Ollama LLM, and Piper TTS.
    3. Streams 8kHz G.711 mu-law audio back to Twilio caller smoothly without breaks.
    """
    await websocket.accept()
    logger.info("WebSocket client connected to /voice/stream.")
    
    stream_sid = None
    caller_phone = "+919876543210" # Default fallback
    pipeline = None
    
    is_bot_speaking = False
    is_processing_turn = False
    stream_start_time = 0.0
    active_playback_task: Optional[asyncio.Task] = None

    async def send_audio_to_twilio(wav_bytes: bytes):
        nonlocal is_bot_speaking
        if not stream_sid or not wav_bytes:
            return
        is_bot_speaking = True
        mulaw_data = wav_bytes_to_mulaw8k(wav_bytes)
        chunk_size = 160 # 20ms at 8kHz
        try:
            for i in range(0, len(mulaw_data), chunk_size):
                chunk = mulaw_data[i:i + chunk_size]
                payload = base64.b64encode(chunk).decode("utf-8")
                msg = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload}
                }
                await websocket.send_text(json.dumps(msg))
                await asyncio.sleep(0.018) # 20ms pacing
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception as err:
            logger.debug(f"Audio send interrupted: {err}")
        finally:
            is_bot_speaking = False
            # Clear VAD buffer so no speaker echo from the phone is processed as caller speech
            if pipeline:
                pipeline.audio_buffer.clear()
                pipeline.is_speaking = False
                pipeline.silence_samples = 0

    async def handle_speech_turn(audio_segment: np.ndarray):
        nonlocal active_playback_task, is_processing_turn
        try:
            logger.info("Processing caller speech with AI pipeline...")
            if pipeline:
                turn_res = await pipeline.execute_turn(audio_segment)
                if turn_res and turn_res.get("wav_bytes"):
                    if active_playback_task and not active_playback_task.done():
                        active_playback_task.cancel()
                    active_playback_task = asyncio.create_task(send_audio_to_twilio(turn_res["wav_bytes"]))
                    await active_playback_task
        except Exception as err:
            logger.error(f"Error handling speech turn: {err}")
        finally:
            is_processing_turn = False

    try:
        while True:
            raw_msg = await websocket.receive_text()
            data = json.loads(raw_msg)
            event_type = data.get("event")
            
            if event_type == "start":
                start_info = data.get("start", {})
                stream_sid = data.get("streamSid") or start_info.get("streamSid")
                custom_params = start_info.get("customParameters", {})
                caller_phone = custom_params.get("caller", caller_phone)
                stream_start_time = asyncio.get_event_loop().time()
                
                logger.info(f"Stream Started: SID={stream_sid}, Caller={caller_phone}")
                
                # Check for Gemini 2.5 Multimodal Live Speech-to-Speech engine
                if settings.GEMINI_API_KEY:
                    logger.info(f"Handing off call for {caller_phone} to Gemini 2.5 Multimodal Live Speech-to-Speech engine!")
                    from src.server.gemini_live_bridge import handle_gemini_live_session
                    await handle_gemini_live_session(websocket, stream_sid, caller_phone)
                    return

                # Local Fallback Mode: lazily initialize local pipeline
                from src.pipeline.bot_pipeline import VoiceBotPipeline
                pipeline = VoiceBotPipeline(
                    caller_phone=caller_phone,
                    stt_service=bot_pipeline.stt if bot_pipeline else None,
                    llm_service=bot_pipeline.llm if bot_pipeline else None,
                    tts_service=bot_pipeline.tts if bot_pipeline else None
                )

                greeting_text, greeting_wav = pipeline.set_caller(caller_phone)
                logger.info(f"Bot Initial Greeting to [{caller_phone}]: {greeting_text}")
                
                # Send immediate welcome greeting unbroken
                if active_playback_task and not active_playback_task.done():
                    active_playback_task.cancel()
                active_playback_task = asyncio.create_task(send_audio_to_twilio(greeting_wav))

            elif event_type == "media":
                # Ignore initial 1.0s of media to discard DTMF tone remnants from Twilio trial keypress
                if (asyncio.get_event_loop().time() - stream_start_time) < 1.0:
                    continue

                # Echo suppression: do NOT buffer microphone audio while bot is actively speaking
                if is_bot_speaking:
                    continue

                payload_b64 = data["media"]["payload"]
                mulaw_bytes = base64.b64decode(payload_b64)
                
                # Decode 8kHz mu-law to float32
                audio_8k = decode_mulaw(mulaw_bytes)
                # Resample to 16kHz for VAD / Whisper
                audio_16k = resample_audio(audio_8k, orig_sr=8000, target_sr=16000)
                
                speech_segment = pipeline.process_audio_chunk(audio_16k)
                if speech_segment is not None and not is_processing_turn:
                    is_processing_turn = True
                    asyncio.create_task(handle_speech_turn(speech_segment))

            elif event_type in ["clear", "dtmf"]:
                pass

            elif event_type == "stop":
                logger.info(f"Stream Stopped for SID {stream_sid}")
                if active_playback_task and not active_playback_task.done():
                    active_playback_task.cancel()
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client.")
    except Exception as e:
        logger.error(f"Error in telephony WebSocket stream: {e}")
    finally:
        logger.info(f"Call session ended for {caller_phone}.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server.telephony_server:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=False)
