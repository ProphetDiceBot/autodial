import asyncio
import re
import numpy as np
from fastapi import WebSocket
from datetime import datetime
import json
import os

from autodial.config import SYSTEM_PROMPT
from autodial.logger import get_logger
from autodial.llm import get_llm_response
from autodial.tts import stream_tts
from autodial.twilio_utils import execute_dtmf, hangup_call
import aiohttp

logger = get_logger("Autodial.Session")

class PhoneSession:
    """Manages state, history, and tasks for a single active phone call."""
    
    def __init__(self, websocket: WebSocket, stream_sid: str, call_sid: str, stt_model, 
                 context: str = None, goals: str = None, keywords: str = None, 
                 broadcast_message: str = None, callback_url: str = None,
                 system_instructions: str = None, provider: str = "twilio"):
        self.ws = websocket
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.stt_model = stt_model
        self.callback_url = callback_url
        self.provider = provider
        
        # Build dynamic system prompt
        full_prompt = SYSTEM_PROMPT
        if system_instructions: full_prompt = f"GUARDRAILS: {system_instructions}\n\n{full_prompt}"
        if context: full_prompt += f"\nCONTEXT: {context}"
        if goals: full_prompt += f"\nGOALS: {goals}"
        if keywords: full_prompt += f"\nKEYWORDS: {keywords}"
        
        self.history = [{"role": "system", "content": full_prompt}]
        self.current_task: asyncio.Task = None
        self.broadcast_message = broadcast_message
        self.termination_keywords = ["stop calling me", "i don't want this call", "don't call me", "goodbye", "quit"]
        
        self.logs_dir = "call_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_file_path = os.path.join(self.logs_dir, f"transcript_{self.call_sid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        self.transcript = []

    def _save_transcript(self):
        try:
            with open(self.log_file_path, "w") as f:
                json.dump({
                    "call_sid": self.call_sid,
                    "stream_sid": self.stream_sid,
                    "transcript": self.transcript
                }, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")

    def log_interaction(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self.transcript.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        })
        self._save_transcript()

    async def process_turn(self, audio_np: np.ndarray):
        """The main interaction pipeline. Handled as a cancelable async task."""
        try:
            if not self.stt_model:
                logger.error("STT Model is not loaded.")
                return

            # 1. Transcribe (Run in thread to avoid blocking WebSocket!)
            segments, _ = await asyncio.to_thread(self.stt_model.transcribe, audio_np, beam_size=1)
            user_text = "".join([segment.text for segment in segments]).strip()
            
            if not user_text:
                return
            
            logger.info(f"[User]: {user_text}")
            
            # Check for termination keywords (case-insensitive)
            text_lower = user_text.lower()
            if any(term in text_lower for term in self.termination_keywords):
                logger.info(f"Termination keyword detected: {user_text}. Hanging up.")
                self.log_interaction("user", user_text)
                self.log_interaction("system", "[AUTO-TERMINATE] Hanging up based on user request.")
                await stream_tts("I understand. Goodbye.", self.ws, self.stream_sid, self.provider)
                await asyncio.sleep(1)
                hangup_call(self.call_sid)
                return

            self.log_interaction("user", user_text)
            
            # 2. LLM Processing
            raw_response = await get_llm_response(self.history)
            self.log_interaction("assistant", raw_response)
            
            # 3. DTMF Extraction & Execution
            spoken_response = raw_response
            dtmf_match = re.search(r'<DTMF:([\d\*\#]+)>', raw_response)
            if dtmf_match:
                digits = dtmf_match.group(1)
                asyncio.create_task(asyncio.to_thread(execute_dtmf, self.call_sid, digits))
                spoken_response = re.sub(r'<DTMF:[\d\*\#]+>', '', raw_response).strip()
            
            # 4. Text-to-Speech Streaming
            if spoken_response:
                await stream_tts(spoken_response, self.ws, self.stream_sid, self.provider)
                
        except asyncio.CancelledError:
            logger.info("[System] Interaction pipeline aborted.")
        except Exception as e:
            logger.error(f"Error in processing turn: {e}", exc_info=True)

    async def process_broadcast(self):
        """Plays a direct message and hangs up the call."""
        try:
            if self.broadcast_message:
                logger.info(f"Broadcasting message: {self.broadcast_message}")
                self.log_interaction("assistant", f"[BROADCAST]: {self.broadcast_message}")
                await stream_tts(self.broadcast_message, self.ws, self.stream_sid, self.provider)
                
                # Small delay to ensure audio is flushed (Twilio side)
                await asyncio.sleep(1)
                
                logger.info("Broadcast complete. Hanging up call.")
                hangup_call(self.call_sid)
        except Exception as e:
            logger.error(f"Error in broadcast: {e}")

    async def finalize_session(self):
        """Sends final transcript to callback_url if provided."""
        if self.callback_url:
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "call_sid": self.call_sid,
                        "stream_sid": self.stream_sid,
                        "timestamp": datetime.now().isoformat(),
                        "transcript": self.transcript,
                        "status": "completed"
                    }
                    async with session.post(self.callback_url, json=payload, timeout=5) as resp:
                        logger.info(f"Callback sent to {self.callback_url} | Status: {resp.status}")
            except Exception as e:
                logger.error(f"Failed to send callback: {e}")
