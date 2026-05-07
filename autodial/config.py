import os
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", 8000))
OLLAMA_CHAT_URL = os.getenv("OLLAMA_CHAT_URL", "http://localhost:11434/api/chat")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

PIPER_MODEL = os.getenv("PIPER_MODEL", "./en_US-lessac-medium.onnx")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

SYSTEM_PROMPT = (
    "You are an AI assistant making an outbound phone call. "
    "Respond conversationally and keep your answers under 2 sentences. "
    "CRITICAL INSTRUCTION: If you hear an automated menu or robot asking you to press a button, "
    "you MUST include the exact digit in your response using this exact format: <DTMF:X> where X is the digit. "
    "Example: 'Navigating menu. <DTMF:1>'"
)
