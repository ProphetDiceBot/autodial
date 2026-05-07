import json
import base64
import audioop
import numpy as np
import asyncio
from typing import List
from pydantic import BaseModel

from fastapi import FastAPI, WebSocket, Request, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
import os
import glob
from dotenv import set_key, find_dotenv

from faster_whisper import WhisperModel

from autodial.config import PORT
from autodial.logger import get_logger
from autodial.session import PhoneSession
from autodial.twilio_utils import dial_out, twilio_client
from autodial.ui import get_dashboard_html

logger = get_logger("Autodial.Server")

global_stt_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Loads heavy models into VRAM cleanly on startup, unloads on shutdown."""
    global global_stt_model
    logger.info("Initializing Faster-Whisper on RTX 3050 Ti (int8 mode)...")
    try:
        global_stt_model = WhisperModel("base.en", device="cuda", compute_type="int8")
        logger.info("Whisper loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load Whisper model on CUDA: {e}")
        logger.info("Falling back to CPU mode for Whisper...")
        try:
             global_stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
             logger.info("Whisper loaded successfully on CPU.")
        except Exception as cpu_e:
             logger.error(f"Failed to load Whisper model on CPU: {cpu_e}")
             global_stt_model = None
    yield
    logger.info("Shutting down. Freeing VRAM...")
    global_stt_model = None

app = FastAPI(title="Professional Local PhoneBot", lifespan=lifespan)

class SubdialRequest(BaseModel):
    to_number: str
    context: str = None
    goals: str = None
    keywords: str = None
    callback_url: str = None
    system_instructions: str = None

class BroadcastRequest(BaseModel):
    numbers: List[str]
    context: str = None
    goals: str = None
    keywords: str = None
    message: str = None
    callback_url: str = None
    system_instructions: str = None

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the main Web GUI Dashboard."""
    return get_dashboard_html()

@app.get("/api/config")
async def get_config():
    """Returns the current configuration, masking sensitive keys for security."""
    from autodial.config import (
        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
        LLM_PROVIDER, LLM_MODEL, OLLAMA_CHAT_URL, 
        OPENAI_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY
    )
    
    def mask(k):
        return k[:4] + "..." + k[-4:] if k and len(k) > 8 else k
        
    return {
        "TWILIO_ACCOUNT_SID": TWILIO_ACCOUNT_SID,
        "TWILIO_AUTH_TOKEN": mask(TWILIO_AUTH_TOKEN),
        "TWILIO_PHONE_NUMBER": TWILIO_PHONE_NUMBER,
        "LLM_PROVIDER": LLM_PROVIDER,
        "LLM_MODEL": LLM_MODEL,
        "OLLAMA_CHAT_URL": OLLAMA_CHAT_URL,
        "OPENAI_API_KEY": mask(OPENAI_API_KEY),
        "GEMINI_API_KEY": mask(GEMINI_API_KEY),
        "MISTRAL_API_KEY": mask(MISTRAL_API_KEY)
    }

@app.post("/api/config")
async def update_config(request: Request):
    """Updates the .env file with new configuration."""
    data = await request.json()
    env_file = find_dotenv()
    if not env_file:
        # Create .env if it doesn't exist
        env_file = ".env"
        open(env_file, 'a').close()
        
    for key, value in data.items():
        # Avoid saving masked passwords back
        if value and "..." not in value:
            set_key(env_file, key, value)
            
    # Note: Changes require a restart to fully take effect across all imports in a real production environment,
    # but the config will be read fresh if we use os.getenv instead of cached imports.
    return {"status": "success"}

@app.get("/api/logs")
async def get_logs():
    """Returns the 10 most recent call logs."""
    logs_dir = "call_logs"
    if not os.path.exists(logs_dir):
        return []
        
    log_files = glob.glob(os.path.join(logs_dir, "*.json"))
    log_files.sort(key=os.path.getmtime, reverse=True)
    
    recent_logs = []
    for file in log_files[:10]:
        try:
            with open(file, "r") as f:
                recent_logs.append(json.load(f))
        except Exception:
            continue
    return recent_logs

@app.post("/incoming")
async def handle_inbound_call(request: Request):
    """Handles incoming calls from Twilio or Telnyx and bridges them to the AI stream."""
    host = request.headers.get("host")
    
    # We output generic XML that works for both Twilio (TwiML) and Telnyx (TeXML)
    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/media-stream" />
    </Connect>
</Response>"""
    return PlainTextResponse(xml_response, media_type="text/xml")

@app.post("/dial")
async def trigger_call(request_data: SubdialRequest, background_tasks: BackgroundTasks, request: Request):
    if not twilio_client:
        raise HTTPException(status_code=500, detail="Twilio not configured.")
    host = request.headers.get("host")
    background_tasks.add_task(dial_out, request_data.to_number, host, 
                              context=request_data.context, 
                              goals=request_data.goals, 
                              keywords=request_data.keywords,
                              callback_url=request_data.callback_url,
                              system_instructions=request_data.system_instructions)
    return {"status": "Dialing sequence initiated", "target": request_data.to_number}

@app.post("/broadcast")
async def trigger_broadcast(request_data: BroadcastRequest, background_tasks: BackgroundTasks, request: Request):
    """Broadcast to multiple phone numbers at once."""
    if not twilio_client:
        raise HTTPException(status_code=500, detail="Twilio not configured.")
    host = request.headers.get("host")
    for number in request_data.numbers:
        background_tasks.add_task(dial_out, number, host, 
                                  context=request_data.context, 
                                  goals=request_data.goals, 
                                  keywords=request_data.keywords,
                                  broadcast_message=request_data.message,
                                  callback_url=request_data.callback_url,
                                  system_instructions=request_data.system_instructions)
    return {"status": "Broadcast sequence initiated", "targets_count": len(request_data.numbers)}

@app.websocket("/media-stream")
async def media_stream_handler(websocket: WebSocket):
    await websocket.accept()
    session: PhoneSession = None
    
    audio_buffer = bytearray()
    SILENCE_THRESHOLD = 500  
    MAX_SILENCE_CHUNKS = 25  # ~500ms
    silence_chunks = 0
    is_speaking = False

    try:
        while True:
            message = await websocket.receive_text()
            packet = json.loads(message)
            
            event_type = packet.get('event')
            
            if event_type == 'start':
                start_data = packet.get('start', {})
                
                # Agnostic parsing for Twilio vs Telnyx
                stream_sid = start_data.get('streamSid') or start_data.get('stream_id')
                call_sid = start_data.get('callSid') or start_data.get('call_control_id') or start_data.get('call_leg_id') or "UnknownCall"
                
                provider = "telnyx" if "stream_id" in start_data else "twilio"
                
                # Extract query parameters for session customization
                params = websocket.query_params
                session = PhoneSession(
                    websocket, 
                    stream_sid, 
                    call_sid, 
                    global_stt_model,
                    context=params.get("context"),
                    goals=params.get("goals"),
                    keywords=params.get("keywords"),
                    broadcast_message=params.get("broadcast_message"),
                    callback_url=params.get("callback_url"),
                    system_instructions=params.get("system_instructions"),
                    provider=provider
                )
                logger.info(f"Stream {stream_sid} connected for Call {call_sid} via {provider.upper()}")
                
                # If it's a broadcast mode with direct message, play it and then hang up
                if params.get("broadcast_message"):
                    asyncio.create_task(session.process_broadcast())
                
            elif event_type == 'media' and session:
                chunk_ulaw = base64.b64decode(packet['media']['payload'])
                
                # U-law to 16kHz PCM
                chunk_pcm_8k = audioop.ulaw2lin(chunk_ulaw, 2)
                chunk_pcm_16k, _ = audioop.ratecv(chunk_pcm_8k, 2, 1, 8000, 16000, None)
                
                energy = audioop.rms(chunk_pcm_16k, 2)
                
                # BARGE-IN & VAD LOGIC
                if energy > SILENCE_THRESHOLD:
                    if not is_speaking:
                        is_speaking = True
                        if session.current_task and not session.current_task.done():
                            session.current_task.cancel()
                    silence_chunks = 0
                    audio_buffer.extend(chunk_pcm_16k)
                    
                elif is_speaking:
                    silence_chunks += 1
                    audio_buffer.extend(chunk_pcm_16k)
                    
                    if silence_chunks > MAX_SILENCE_CHUNKS:
                        is_speaking = False
                        
                        # Only process if we have more than 0.5s of audio (8000 bytes at 16kHz)
                        if len(audio_buffer) > 8000:
                            audio_np = np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
                            
                            session.current_task = asyncio.create_task(
                                session.process_turn(audio_np)
                            )
                        
                        audio_buffer.clear()
                        silence_chunks = 0
                        
            elif event_type == 'stop':
                logger.info("Twilio Stream Stopped.")
                break
                
    except asyncio.exceptions.TimeoutError:
        logger.warning("WebSocket timeout.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
    finally:
        if session:
            if session.current_task and not session.current_task.done():
                session.current_task.cancel()
            # Ensure callback is fired
            await session.finalize_session()
        await websocket.close()

def start_server(host="0.0.0.0", port=int(PORT)):
    import uvicorn
    uvicorn.run("autodial.server:app", host=host, port=port, access_log=False)

if __name__ == "__main__":
    start_server()
