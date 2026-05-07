import os
import sys
import json
import base64
import asyncio
import audioop
import re
import logging
import numpy as np
import aiohttp
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request, BackgroundTasks, HTTPException
from fastapi.responses import Response
from twilio.rest import Client
from faster_whisper import WhisperModel

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PhoneBot")

# Environment Variables
PORT = int(os.getenv("PORT", 8000))
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
PIPER_MODEL = os.getenv("PIPER_MODEL", "./en_US-lessac-medium.onnx")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    logger.warning("Twilio credentials missing. Outbound dialing will fail.")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

SYSTEM_PROMPT = (
    "You are an AI assistant making an outbound phone call. "
    "Respond conversationally and keep your answers under 2 sentences. "
    "CRITICAL INSTRUCTION: If you hear an automated menu or robot asking you to press a button, "
    "you MUST include the exact digit in your response using this exact format: <DTMF:X> where X is the digit. "
    "Example: 'Navigating menu. <DTMF:1>'"
)

# Global Model Reference
global_stt_model = None

# ==========================================
# LIFECYCLE MANAGEMENT
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Loads heavy models into VRAM cleanly on startup, unloads on shutdown."""
    global global_stt_model
    logger.info("Initializing Faster-Whisper on RTX 3050 Ti (int8 mode)...")
    global_stt_model = WhisperModel("base.en", device="cuda", compute_type="int8")
    logger.info("Whisper loaded successfully.")
    yield
    logger.info("Shutting down. Freeing VRAM...")
    global_stt_model = None

app = FastAPI(title="Professional Local PhoneBot", lifespan=lifespan)

# ==========================================
# CORE BOT LOGIC
# ==========================================
class PhoneSession:
    """Manages state, history, and tasks for a single active phone call."""
    
    def __init__(self, websocket: WebSocket, stream_sid: str, call_sid: str):
        self.ws = websocket
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.current_task: asyncio.Task = None

    async def get_llm_response(self) -> str:
        payload = {"model": LLM_MODEL, "messages": self.history, "stream": False}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(OLLAMA_CHAT_URL, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("message", {}).get("content", "")
                    logger.error(f"LLM API Error: {response.status}")
                    return "I'm having trouble thinking right now."
        except asyncio.TimeoutError:
            logger.error("LLM timeout.")
            return "My connection timed out."
        except asyncio.CancelledError:
            raise

    async def stream_tts(self, text: str):
        logger.info(f"[Bot] Speaks: {text}")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "piper", "--model", PIPER_MODEL, "--output_raw",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        try:
            process.stdin.write(text.encode('utf-8'))
            await process.stdin.drain()
            process.stdin.close()
            
            while True:
                pcm_data = await process.stdout.read(4096)
                if not pcm_data:
                    break
                    
                # Downsample 16kHz PCM to 8kHz, then to u-law
                pcm_8k, _ = audioop.ratecv(pcm_data, 2, 1, 16000, 8000, None)
                ulaw_data = audioop.lin2ulaw(pcm_8k, 2)
                
                await self.ws.send_text(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": base64.b64encode(ulaw_data).decode("utf-8")}
                }))
            
            await process.wait()
            
        except asyncio.CancelledError:
            logger.info("[TTS] Playback cancelled (Barge-in). Terminating Piper.")
            process.terminate()
            # Clear Twilio's audio queue
            await self.ws.send_text(json.dumps({
                "event": "clear",
                "streamSid": self.stream_sid
            }))
            raise

    def execute_dtmf(self, digits: str):
        if not twilio_client or not self.call_sid:
            return
        try:
            formatted_digits = f"w{digits}w" 
            twilio_client.calls(self.call_sid).update(send_digits=formatted_digits)
            logger.info(f"[Twilio] Injected DTMF: {digits} into Call: {self.call_sid}")
        except Exception as e:
            logger.error(f"[Twilio] DTMF Failed: {e}")

    async def process_turn(self, audio_np: np.ndarray):
        """The main interaction pipeline. Handled as a cancelable async task."""
        try:
            # 1. Transcribe (Run in thread to avoid blocking WebSocket!)
            segments, _ = await asyncio.to_thread(global_stt_model.transcribe, audio_np, beam_size=1)
            user_text = "".join([segment.text for segment in segments]).strip()
            
            if not user_text:
                return
            
            logger.info(f"[User]: {user_text}")
            self.history.append({"role": "user", "content": user_text})
            
            # 2. LLM Processing
            raw_response = await self.get_llm_response()
            self.history.append({"role": "assistant", "content": raw_response})
            
            # 3. DTMF Extraction & Execution
            spoken_response = raw_response
            dtmf_match = re.search(r'<DTMF:([\d\*\#]+)>', raw_response)
            if dtmf_match:
                digits = dtmf_match.group(1)
                asyncio.create_task(asyncio.to_thread(self.execute_dtmf, digits))
                spoken_response = re.sub(r'<DTMF:[\d\*\#]+>', '', raw_response).strip()
            
            # 4. Text-to-Speech Streaming
            if spoken_response:
                await self.stream_tts(spoken_response)
                
        except asyncio.CancelledError:
            logger.info("[System] Interaction pipeline aborted.")
        except Exception as e:
            logger.error(f"Error in processing turn: {e}", exc_info=True)


# ==========================================
# REST & WEBSOCKET ENDPOINTS
# ==========================================
def dial_out(target_number: str, host: str):
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/media-stream" />
    </Connect>
</Response>"""
    try:
        call = twilio_client.calls.create(
            twiml=twiml, to=target_number, from_=TWILIO_PHONE_NUMBER
        )
        logger.info(f"Dialing {target_number} | SID: {call.sid}")
    except Exception as e:
        logger.error(f"Dialing failed: {e}")

@app.post("/dial")
async def trigger_call(to_number: str, background_tasks: BackgroundTasks, request: Request):
    if not twilio_client:
        raise HTTPException(status_code=500, detail="Twilio not configured.")
    host = request.headers.get("host")
    background_tasks.add_task(dial_out, to_number, host)
    return {"status": "Dialing sequence initiated", "target": to_number}


@app.websocket("/media-stream")
async def media_stream_handler(websocket: WebSocket):
    await websocket.accept()
    session: PhoneSession = None
    
    # Audio buffer parameters
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
                stream_sid = packet['start']['streamSid']
                call_sid = packet['start'].get('callSid')
                session = PhoneSession(websocket, stream_sid, call_sid)
                logger.info(f"Stream {stream_sid} connected for Call {call_sid}")
                
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
                            
                            # Dispatch turn to the background task
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
        if session and session.current_task and not session.current_task.done():
            session.current_task.cancel()
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, access_log=False)