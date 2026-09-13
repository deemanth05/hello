# API & Telephony Protocol Reference

This document provides a comprehensive specification of all HTTP endpoints and WebSocket streaming protocols exposed by the DMart Express Voice-AI Telephony Server.

---

## 1. REST Endpoints

### `GET /health`
Verifies server health, running store configuration, and the active LLM backend.

- **Request Method**: `GET`
- **Request Headers**: None required
- **Response Format**: `application/json`
- **Response Example**:
```json
{
  "status": "healthy",
  "store": "D mart Express",
  "model": "gemma3:latest"
}
```

---

### `GET /api/customers`
Retrieves all registered customer profiles from the database.

- **Request Method**: `GET`
- **Response Format**: `application/json`
- **Response Example**:
```json
{
  "customers": [
    {
      "id": 1,
      "phone_number": "+919876543210",
      "name": "Rahul Sharma",
      "address": "Flat 402, Sunshine Heights, Mumbai",
      "created_at": "2026-09-10 18:30:00"
    }
  ]
}
```

---

### `GET /api/products`
Searches store inventory by name, category, or semantic keyword.

- **Request Method**: `GET`
- **Query Parameters**:
  - `query` *(optional, string)*: Filter keyword (e.g. `milk`, `ಹಾಲು`, `oil`, `sugar`).
- **Response Format**: `application/json`
- **Response Example**:
```json
{
  "products": [
    {
      "id": 11,
      "name": "Amul Taaza Toned Milk 1L",
      "category": "Dairy",
      "price": 54.0,
      "unit": "1 Liter",
      "stock_quantity": 50
    }
  ]
}
```

---

### `GET /api/orders/{order_id}`
Retrieves complete details of an existing order including line items and dynamic delivery ETA.

- **Request Method**: `GET`
- **Path Parameters**:
  - `order_id` *(required, string)*: Order identifier (e.g. `DMART-A045`).
- **Response Format**: `application/json`
- **Response Example**:
```json
{
  "found": true,
  "id": 4,
  "order_id": "DMART-A045",
  "customer_name": "Vikram Rao",
  "customer_phone": "+919999888877",
  "delivery_type": "delivery",
  "delivery_address": "Flat 101, Palm Grove Apartments, Indiranagar, Bangalore",
  "total_amount": 443.0,
  "estimated_delivery_time": "30 to 40 minutes (approx 9:45 PM)",
  "status": "CONFIRMED",
  "created_at": "2026-09-10 21:10:50",
  "items": [
    {
      "product_name": "Fortune Sunlite Sunflower Oil 1L",
      "quantity": 1,
      "unit_price": 140.0,
      "subtotal": 140.0
    }
  ]
}
```

---

### `POST /api/register`
Manually registers or updates a customer profile.

- **Request Method**: `POST`
- **Request Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "phone": "+919555444333",
  "name": "Kavita Rao",
  "address": "Brigade Gateway, Rajajinagar, Bengaluru"
}
```
- **Response Example**:
```json
{
  "success": true,
  "customer_id": 25,
  "name": "Kavita Rao",
  "phone_number": "+919555444333",
  "address": "Brigade Gateway, Rajajinagar, Bengaluru",
  "message": "Customer registered successfully."
}
```

---

## 2. Twilio Telephony Webhook

### `POST|GET /voice/incoming`
Webhook endpoint called by Twilio when an inbound phone call arrives at your registered Twilio phone number.

- **Supported Methods**: `POST` (standard Twilio production), `GET` (browser test)
- **Twilio Form Data Parameters**:
  - `From`: Caller phone number in E.164 format (e.g. `+919876543210`).
  - `To`: Twilio virtual phone number.
  - `CallSid`: Unique identifier for the Twilio call session.
- **Response Type**: `application/xml` (TwiML)
- **Response Structure**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://your-domain.ngrok-free.app/voice/stream">
            <Parameter name="caller" value="+919876543210" />
        </Stream>
    </Connect>
</Response>
```

> [!NOTE]
> The server inspects request headers (`Host` and `X-Forwarded-Proto`) to automatically negotiate between insecure `ws://` and TLS-secured `wss://` URLs for Twilio compliance.

---

## 3. Bi-Directional WebSocket Streaming (`/voice/stream`)

Twilio connects to `/voice/stream` over WebSocket to exchange bidirectional real-time audio.

### A. Inbound Messages (Twilio $\to$ Server)

#### 1. `start` Event
Sent by Twilio upon stream connection.
```json
{
  "event": "start",
  "sequenceNumber": "1",
  "start": {
    "streamSid": "MZ...",
    "accountSid": "AC...",
    "callSid": "CA...",
    "tracks": ["inbound"],
    "customParameters": {
      "caller": "+919876543210"
    },
    "mediaFormat": {
      "encoding": "audio/x-mulaw",
      "sampleRate": 8000,
      "channels": 1
    }
  },
  "streamSid": "MZ..."
}
```
**Server Action**:
- Extracts `streamSid` and `caller`.
- Initializes conversation session for caller.
- Synthesizes and sends immediate welcome greeting.

#### 2. `media` Event
Sent periodically (every 20ms) containing 160 bytes of base64-encoded G.711 $\mu$-law audio.
```json
{
  "event": "media",
  "sequenceNumber": "24",
  "media": {
    "track": "inbound",
    "chunk": "24",
    "timestamp": "480",
    "payload": "fn5+fn5+fn5..."
  },
  "streamSid": "MZ..."
}
```
**Server Action**:
- Decodes base64 payload to 8-bit $\mu$-law.
- Transcodes to 16kHz linear float32 PCM.
- Feeds energy VAD buffer.

#### 3. `stop` Event
Sent when the caller hangs up.
```json
{
  "event": "stop",
  "sequenceNumber": "450",
  "stop": {
    "accountSid": "AC...",
    "callSid": "CA..."
  },
  "streamSid": "MZ..."
}
```
**Server Action**: Cancels active audio playback and closes session state.

---

### B. Outbound Messages (Server $\to$ Twilio)

#### 1. `media` Event (Spoken Audio)
Streams synthesized audio back to the caller's handset in 20ms chunks (160 bytes of 8kHz $\mu$-law per chunk).
```json
{
  "event": "media",
  "streamSid": "MZ...",
  "media": {
    "payload": "fn5+fn5+..."
  }
}
```
- Audio chunks are spaced at approximately 18–20ms intervals to prevent buffer underrun or packet congestion on Twilio.

#### 2. `clear` Event (Barge-in / Interrupt)
Flushes Twilio's internal audio queue when the caller speaks while the bot is talking (Gemini Live mode).
```json
{
  "event": "clear",
  "streamSid": "MZ..."
}
```
