# Deployment & Operations Guide

This guide covers operational requirements, hardware sizing, environment configuration, and production hosting for the DMart Express Voice-AI Telephony System.

---

## 1. System Requirements

### Hardware Sizing

| Component | Minimum (Local CPU) | Recommended (Local GPU) | Cloud Native (Gemini Mode) |
| :--- | :--- | :--- | :--- |
| **CPU** | 4-Core Intel/AMD (x86_64) | 8-Core Intel/AMD | 2-Core Virtual Machine |
| **RAM** | 8 GB System RAM | 16 GB System RAM | 2 GB System RAM |
| **GPU / VRAM** | Not required (CPU `int8`) | NVIDIA 6GB+ VRAM (CUDA) | Not required |
| **Storage** | 10 GB free disk space | 15 GB free disk space | 1 GB free disk space |
| **OS** | Windows 10/11, Ubuntu 20.04+, Debian 11+ | Same | Linux / Docker / Cloud Run |

---

## 2. Production Running Commands

### Starting the Uvicorn Telephony Server

#### Direct Execution
```powershell
.venv\Scripts\python.exe -m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8765 --workers 1
```

> [!IMPORTANT]
> Because the local pipeline maintains in-memory audio buffers and loads ONNX models, run with a single worker (`--workers 1`) per server instance, or use horizontal scaling behind a sticky load balancer.

---

### Running as a Windows Service (NSSM)

On Windows, use [NSSM (Non-Sucking Service Manager)](https://nssm.cc/) to ensure the server restarts automatically on reboot:

```cmd
nssm install DMartVoiceAI "C:\Users\deema\Desktop\hello\.venv\Scripts\python.exe" "-m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8765"
nssm set DMartVoiceAI AppDirectory "C:\Users\deema\Desktop\hello"
nssm start DMartVoiceAI
```

---

### Running as a Linux Systemd Service

Create `/etc/systemd/system/dmart-voice.service`:

```ini
[Unit]
Description=DMart Express Voice AI Telephony Service
After=network.target ollama.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/dmart-voice
ExecStart=/opt/dmart-voice/.venv/bin/python -m uvicorn src.server.telephony_server:app --host 0.0.0.0 --port 8765
Restart=always
RestartSec=5
EnvironmentFile=/opt/dmart-voice/.env

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dmart-voice
sudo systemctl start dmart-voice
```

---

## 3. Environment Variables Reference

| Variable | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `STORE_NAME` | String | `D mart Express` | Spoken brand name announced by the AI |
| `STORE_PHONE` | String | `+17744930623` | Store contact number |
| `MINIMUM_ORDER_VALUE`| Float | `250.0` | Minimum purchase threshold (INR ₹) |
| `DELIVERY_FEE` | Float | `30.0` | Delivery charge (INR ₹) |
| `FREE_DELIVERY_THRESHOLD`| Float | `800.0` | Minimum spend for free delivery |
| `OLLAMA_HOST` | String | `http://localhost:11434` | Ollama API address |
| `OLLAMA_MODEL` | String | `gemma3:latest` | Local LLM model name |
| `LANGUAGE` | String | `kn` | Primary language code (`kn` for Kannada) |
| `STT_MODEL_SIZE` | String | `base` | Faster-Whisper model (`tiny`, `base`, `small`) |
| `STT_LANGUAGE` | String | `kn` | STT language code |
| `SERVER_HOST` | String | `0.0.0.0` | FastAPI server bind address |
| `SERVER_PORT` | Integer| `8765` | Server port |
| `GEMINI_API_KEY` | String | `""` | Optional: activates Gemini 2.5 Live bridge |
| `TWILIO_ACCOUNT_SID` | String | `""` | Twilio Account SID for setup script |
| `TWILIO_AUTH_TOKEN` | String | `""` | Twilio Auth Token for setup script |

---

## 4. Performance & Latency Optimization

1. **Ollama GPU Acceleration**: If an NVIDIA GPU is available, ensure Ollama detects CUDA. This reduces LLM token generation latency from ~300ms/token to ~20ms/token.
2. **Whisper Quantization**: The pipeline defaults to `compute_type="int8"`. If running on an NVIDIA GPU, modify `src/services/stt_service.py` to use `float16`.
3. **Pacing Audio Chunks**: Twilio expects 20ms audio frames. Outbound packets are spaced by 18–20ms to match the clock rate of telecom switches.
