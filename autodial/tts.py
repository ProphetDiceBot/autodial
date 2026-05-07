import asyncio
import sys
import json
import base64
import audioop
from autodial.config import PIPER_MODEL
from autodial.logger import get_logger
from fastapi import WebSocket

logger = get_logger("Autodial.TTS")

async def stream_tts(text: str, websocket: WebSocket, stream_sid: str, provider: str = "twilio") -> asyncio.subprocess.Process:
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
            
            # Construct provider-agnostic payload
            media_message = {
                "event": "media",
                "media": {"payload": base64.b64encode(ulaw_data).decode("utf-8")}
            }
            if provider == "twilio":
                media_message["streamSid"] = stream_sid
            elif provider == "telnyx":
                media_message["stream_id"] = stream_sid
                
            await websocket.send_text(json.dumps(media_message))
        
        await process.wait()
        return process
        
    except asyncio.CancelledError:
        logger.info("[TTS] Playback cancelled (Barge-in). Terminating Piper.")
        if process.returncode is None:
            process.terminate()
        # Clear Twilio/Telnyx audio queue
        clear_msg = {"event": "clear"}
        if provider == "twilio":
            clear_msg["streamSid"] = stream_sid
        elif provider == "telnyx":
            clear_msg["stream_id"] = stream_sid
            
        await websocket.send_text(json.dumps(clear_msg))
        raise
