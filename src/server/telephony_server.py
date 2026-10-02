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
from src.database.db import init_db
from src.database.customer_repo import (
    get_customer, list_all_customers, register_customer,
    update_customer, delete_customer, get_customer_orders_by_phone
)
from src.database.booking_repo import (
    search_products, get_order_details, list_recent_orders,
    add_product, update_product, delete_product, update_product_stock,
    update_order_status, cancel_order, get_dashboard_stats, place_order
)
from src.database.settings_repo import (
    get_all_settings, get_setting, update_settings, update_setting
)
from src.database.call_log_repo import list_recent_calls
from src.server.audio_utils import decode_mulaw, resample_audio, wav_bytes_to_mulaw8k

app = FastAPI(title="DMart Express Voice AI Telephony & Management Server", version="2.5.0")

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
    store_name = get_setting("store_name", settings.STORE_NAME)
    return {
        "status": "healthy",
        "version": "2.5.1",
        "store": store_name,
        "model": "gemini-2.5-flash-native-audio-latest" if settings.GEMINI_API_KEY else settings.OLLAMA_MODEL
    }

# ----------------- DASHBOARD & STORE SETTINGS -----------------

@app.get("/api/dashboard/stats")
async def api_dashboard_stats():
    """Returns aggregated real-time store stats (revenue, orders today, low stock)."""
    return get_dashboard_stats()

@app.get("/api/settings")
async def api_get_settings():
    """Returns all configurable store settings."""
    return get_all_settings()

@app.put("/api/settings")
async def api_update_settings(data: dict):
    """Updates store settings (e.g. store_name, phone, delivery_fee)."""
    update_settings(data)
    return {"success": True, "message": "Settings updated successfully.", "data": get_all_settings()}

# ----------------- PRODUCTS & INVENTORY CRUD -----------------

@app.get("/api/products")
async def api_products(query: str = "", category: str = "", low_stock: bool = False):
    """Search/filter products in the catalog."""
    return {"products": search_products(query=query, category=category, low_stock_only=low_stock)}

@app.post("/api/products")
async def api_create_product(data: dict):
    """Add a new product to the supermarket catalog."""
    res = add_product(
        name=data.get("name", ""),
        category=data.get("category", "Groceries"),
        price=float(data.get("price", 0)),
        unit=data.get("unit", "1 packet"),
        stock_quantity=int(data.get("stock_quantity", 50))
    )
    return res

@app.put("/api/products/{product_id}")
async def api_update_product(product_id: int, data: dict):
    """Update product details (name, category, price, unit, stock)."""
    return update_product(
        product_id=product_id,
        name=data.get("name", ""),
        category=data.get("category", "Groceries"),
        price=float(data.get("price", 0)),
        unit=data.get("unit", "1 packet"),
        stock_quantity=int(data.get("stock_quantity", 0))
    )

@app.delete("/api/products/{product_id}")
async def api_delete_product(product_id: int):
    """Delete a product from the catalog."""
    return delete_product(product_id)

@app.patch("/api/products/{product_id}/stock")
async def api_patch_stock(product_id: int, data: dict):
    """Quick increment or decrement of product inventory."""
    delta = int(data.get("delta", 0))
    return update_product_stock(product_id, delta)

# ----------------- CUSTOMER REGISTRY CRUD -----------------

@app.get("/api/customers")
async def api_customers(query: str = ""):
    """List registered customers with optional search."""
    return {"customers": list_all_customers(query=query)}

@app.post("/api/customers")
@app.post("/api/register")
async def api_register(data: dict):
    """Register or update a customer profile."""
    phone = data.get("phone") or data.get("phone_number", "")
    name = data.get("name", "")
    address = data.get("address", "")
    return register_customer(phone_number=phone, name=name, address=address)

@app.put("/api/customers/{customer_id}")
async def api_update_customer(customer_id: int, data: dict):
    """Edit an existing customer's name, phone, or address."""
    phone = data.get("phone") or data.get("phone_number", "")
    name = data.get("name", "")
    address = data.get("address", "")
    return update_customer(customer_id=customer_id, phone_number=phone, name=name, address=address)

@app.delete("/api/customers/{customer_id}")
async def api_delete_customer(customer_id: int):
    """Delete a customer profile."""
    return delete_customer(customer_id)

@app.get("/api/customers/{customer_id}/orders")
async def api_customer_orders(customer_id: int):
    """Retrieve all past orders placed by this customer."""
    customers = list_all_customers()
    target = next((c for c in customers if c["id"] == customer_id), None)
    if not target:
        return {"orders": []}
    return {"orders": get_customer_orders_by_phone(target["phone_number"])}

# ----------------- ORDERS MANAGEMENT -----------------

@app.get("/api/orders")
async def api_list_orders(status: str = "", limit: int = 50):
    """List recent customer orders."""
    return {"orders": list_recent_orders(limit=limit, status_filter=status)}

@app.get("/api/orders/{order_id}")
async def api_order(order_id: str):
    """Fetch order details and line items."""
    return get_order_details(order_id)

@app.post("/api/orders")
async def api_create_order(data: dict):
    """Manually place an order from the dashboard for a walk-in or manual caller."""
    return place_order(
        customer_phone=data.get("customer_phone", ""),
        customer_name=data.get("customer_name", "Walk-in Customer"),
        delivery_type=data.get("delivery_type", "delivery"),
        delivery_address=data.get("delivery_address", ""),
        items=data.get("items", [])
    )

@app.patch("/api/orders/{order_id}/status")
async def api_update_order_status(order_id: str, data: dict):
    """Progress order status (CONFIRMED -> PREPARING -> OUT_FOR_DELIVERY -> DELIVERED -> CANCELLED)."""
    status = data.get("status", "")
    return update_order_status(order_id, status)

@app.post("/api/orders/{order_id}/cancel")
async def api_cancel_order(order_id: str):
    """Cancel order and automatically restore stock to catalog."""
    return cancel_order(order_id)

# ----------------- TELEPHONY & CALL LOGS -----------------

@app.get("/api/calls")
async def api_calls(limit: int = 50):
    """List recent incoming phone calls."""
    return {"calls": list_recent_calls(limit=limit)}

# ----------------- ASSISTANT PLAYGROUND & SIMULATOR -----------------

@app.post("/api/test/chat")
async def api_test_chat(data: dict):
    """
    Browser assistant test: works in all environments (Render cloud & local).
    Uses Gemini API with full tool calling if key is present, else falls back cleanly.
    """
    caller_phone = data.get("caller_phone", "+919876543210")
    message = data.get("message", "").strip()
    if not message:
        return {"success": False, "reply": "Please enter a message."}
        
    if settings.GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types
            from src.server.gemini_live_bridge import GEMINI_TOOLS, build_gemini_instruction, execute_tool_call
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            instruction = build_gemini_instruction(caller_phone)
            
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    tools=GEMINI_TOOLS,
                    temperature=0.3
                )
            )
            
            reply_text = resp.text or ""
            executed_tools = []
            if resp.function_calls:
                for call in resp.function_calls:
                    t_res = execute_tool_call(call.name, dict(call.args), default_phone=caller_phone)
                    executed_tools.append({"name": call.name, "result": t_res})
                    
                # If model only called functions without text, get natural language follow-up
                if not reply_text:
                    followup_prompt = f"Tools executed: {executed_tools}. Respond to the customer warmly in Kannada based on these results."
                    f_resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=followup_prompt,
                        config=types.GenerateContentConfig(system_instruction=instruction, temperature=0.3)
                    )
                    reply_text = f_resp.text or "ಆರ್ಡರ್ ಪ್ರಕ್ರಿಯೆ ಪೂರ್ಣಗೊಂಡಿದೆ."
                    
            return {"success": True, "reply": reply_text, "tools": executed_tools}
        except Exception as e:
            logger.error(f"Gemini test chat error: {e}", exc_info=True)
            return {"success": False, "reply": f"Gemini error: {str(e)}"}
    else:
        if bot_pipeline:
            pipeline = sim_sessions.get(caller_phone)
            if not pipeline:
                from src.pipeline.bot_pipeline import VoiceBotPipeline
                pipeline = VoiceBotPipeline(
                    caller_phone=caller_phone,
                    stt_service=bot_pipeline.stt,
                    llm_service=bot_pipeline.llm,
                    tts_service=bot_pipeline.tts
                )
                sim_sessions[caller_phone] = pipeline
                pipeline.set_caller(caller_phone)
            turn_res = await pipeline.execute_text_turn(message)
            return {"success": True, "reply": turn_res["reply_text"]}
        return {"success": True, "reply": f"Echo test: {message}"}

@app.post("/api/simulate/call")
async def api_simulate_call(data: dict):
    phone = data.get("caller_phone", "+919876543210")
    cust = get_customer(phone)
    store_name = get_setting("store_name", settings.STORE_NAME)
    if cust:
        greeting = f"ನಮಸ್ಕಾರ {cust['name']}, {store_name} ಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ ಇಂದು ಯಾವ ದಿನಸಿ ಸಾಮಗ್ರಿಗಳು ಬೇಕು?"
    else:
        greeting = f"ನಮಸ್ಕಾರ! {store_name} ಗೆ ಸ್ವಾಗತ. ನಿಮ್ಮ ಮೊಬೈಲ್ ನಂಬರ್ ನೋಂದಣಿ ಆಗಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹೆಸರು ಮತ್ತು ವಿಳಾಸ ತಿಳಿಸುತ್ತೀರಾ?"
    return {
        "caller_phone": phone,
        "customer": cust,
        "greeting_text": greeting,
        "audio_base64": None
    }

@app.post("/api/simulate/turn")
async def api_simulate_turn(data: dict):
    phone = data.get("caller_phone", "+919876543210")
    user_text = data.get("text", "")
    res = await api_test_chat({"caller_phone": phone, "message": user_text})
    return {
        "transcript": user_text,
        "reply_text": res.get("reply", ""),
        "audio_base64": None
    }



@app.api_route("/voice/incoming", methods=["GET", "POST"])
@app.api_route("/voice", methods=["GET", "POST"])
@app.api_route("/twiml", methods=["GET", "POST"])
@app.api_route("/incoming", methods=["GET", "POST"])
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
    
    if call_sid:
        try:
            from src.database.call_log_repo import log_call_start
            cust = get_customer(caller)
            log_call_start(call_sid=call_sid, caller_phone=caller, customer_name=cust['name'] if cust else "Caller")
        except Exception as err:
            logger.error(f"Error logging incoming call start: {err}")
    
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="caller" value="{caller}" />
            <Parameter name="call_sid" value="{call_sid}" />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml_response, media_type="text/xml")

@app.websocket("/voice/stream")
@app.websocket("/ws/telephony")
@app.websocket("/stream")
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
                call_sid = custom_params.get("call_sid") or start_info.get("callSid") or stream_sid
                stream_start_time = asyncio.get_event_loop().time()
                
                logger.info(f"Stream Started: SID={stream_sid}, CallSID={call_sid}, Caller={caller_phone}")
                
                # Check for Gemini 2.5 Multimodal Live Speech-to-Speech engine
                if settings.GEMINI_API_KEY:
                    logger.info(f"Handing off call for {caller_phone} to Gemini 2.5 Multimodal Live Speech-to-Speech engine!")
                    from src.server.gemini_live_bridge import handle_gemini_live_session
                    try:
                        await handle_gemini_live_session(websocket, stream_sid, caller_phone, call_sid=call_sid)
                        return
                    except Exception as live_err:
                        logger.error(f"Gemini Live session error: {live_err}, falling back to local voice pipeline...", exc_info=True)

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
