import aiohttp
import asyncio
from typing import List, Dict
from autodial.config import (
    OLLAMA_CHAT_URL, LLM_MODEL, LLM_PROVIDER,
    OPENAI_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY
)
from autodial.logger import get_logger

logger = get_logger("Autodial.LLM")

async def get_llm_response(history: List[Dict[str, str]]) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            if LLM_PROVIDER == "openai":
                if not OPENAI_API_KEY:
                    logger.error("OPENAI_API_KEY is missing.")
                    return "I am unable to think because my API key is missing."
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
                payload = {"model": LLM_MODEL, "messages": history}
                async with session.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.error(f"OpenAI API Error: {response.status} {await response.text()}")
            
            elif LLM_PROVIDER == "mistral":
                if not MISTRAL_API_KEY:
                    logger.error("MISTRAL_API_KEY is missing.")
                    return "I am unable to think because my API key is missing."
                headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
                payload = {"model": LLM_MODEL, "messages": history}
                async with session.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    logger.error(f"Mistral API Error: {response.status} {await response.text()}")
                    
            elif LLM_PROVIDER == "gemini":
                if not GEMINI_API_KEY:
                    logger.error("GEMINI_API_KEY is missing.")
                    return "I am unable to think because my API key is missing."
                
                # Transform history for Gemini
                contents = []
                system_instruction = None
                for msg in history:
                    if msg["role"] == "system":
                        system_instruction = {"parts": [{"text": msg["content"]}]}
                    else:
                        role = "model" if msg["role"] == "assistant" else "user"
                        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
                        
                payload = {"contents": contents}
                if system_instruction:
                    payload["system_instruction"] = system_instruction
                    
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={GEMINI_API_KEY}"
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            return data["candidates"][0]["content"]["parts"][0]["text"]
                        except (KeyError, IndexError):
                            return "I failed to generate a response."
                    logger.error(f"Gemini API Error: {response.status} {await response.text()}")

            else:
                # Default to Ollama
                payload = {"model": LLM_MODEL, "messages": history, "stream": False}
                async with session.post(OLLAMA_CHAT_URL, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("message", {}).get("content", "")
                    logger.error(f"Ollama API Error: {response.status}")
                    
        return "I'm having trouble thinking right now."
    except asyncio.TimeoutError:
        logger.error("LLM timeout.")
        return "My connection timed out."
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"LLM Unexpected Error: {e}", exc_info=True)
        return "I'm having unexpected trouble."
