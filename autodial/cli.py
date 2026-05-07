import sys
import requests
import json
from autodial.config import (
    OLLAMA_CHAT_URL, LLM_MODEL, LLM_PROVIDER,
    OPENAI_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY
)
from autodial.client import AutodialClient
from autodial.server import start_server
from autodial.logger import get_logger

logger = get_logger("Autodial.CLI")

def parse_nlp_command(prompt: str) -> dict:
    """Uses the configured LLM to extract target number, context, and goals from plain text."""
    system_prompt = (
        "You are an AI command parser. Extract the target phone number, context, and goals "
        "from the user's input. Return exactly valid JSON with the keys: "
        "'target_number', 'context', and 'goals'. "
        "If a key is not found or ambiguous, return null for that key. "
        "Ensure the phone number is formatted correctly (e.g. start with + if possible, or leave as provided)."
    )
    
    try:
        if LLM_PROVIDER == "openai":
            if not OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY missing.")
                return None
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            payload = {
                "model": LLM_MODEL,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            }
            res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
            res.raise_for_status()
            content = res.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
            return json.loads(content)
            
        elif LLM_PROVIDER == "mistral":
            if not MISTRAL_API_KEY:
                logger.error("MISTRAL_API_KEY missing.")
                return None
            headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": LLM_MODEL,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            }
            res = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=15)
            res.raise_for_status()
            content = res.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
            return json.loads(content)
            
        elif LLM_PROVIDER == "gemini":
            if not GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY missing.")
                return None
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            res = requests.post(url, json=payload, timeout=15)
            res.raise_for_status()
            content = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content)

        else:
            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "format": "json"
            }
            response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=15)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "{}")
            return json.loads(content)
            
    except Exception as e:
        logger.error(f"Failed to parse NLP command: {e}")
        return None

def main():
    if len(sys.argv) == 1 or sys.argv[1] == "serve":
        logger.info("Starting Autodial server...")
        start_server()
        return
        
    if sys.argv[1] == "gui":
        import webbrowser
        import threading
        import time
        from autodial.config import PORT
        
        logger.info("Starting Autodial Web GUI...")
        def open_browser():
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{PORT}")
            
        threading.Thread(target=open_browser, daemon=True).start()
        start_server()
        return
        
    # Treat all arguments as an NLP command
    command_text = " ".join(sys.argv[1:])
    
    logger.info(f"Parsing NLP Command: '{command_text}' using {LLM_PROVIDER.upper()}")
    parsed = parse_nlp_command(command_text)
    
    if not parsed:
        logger.error("Failed to extract intent from command.")
        return
        
    target_number = parsed.get("target_number")
    context = parsed.get("context")
    goals = parsed.get("goals")
    
    if not target_number:
        logger.error("Could not identify a target phone number in your command.")
        return
        
    logger.info(f"Extracted Target: {target_number}")
    logger.info(f"Extracted Context: {context}")
    logger.info(f"Extracted Goals: {goals}")
    
    client = AutodialClient("http://localhost:8000")
    logger.info("Dispatching call to local server...")
    
    try:
        res = client.dial(
            target_number=target_number,
            context=context,
            goals=goals
        )
        logger.info(f"Success: {res}")
    except Exception as e:
        logger.error(f"Failed to place call via API (is the server running?): {e}")

if __name__ == "__main__":
    main()
