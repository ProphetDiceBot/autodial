<div align="center">
  <h1>📞 Autodial PhoneBot</h1>
  <p><b>The Ultimate Self-Hosted AI Dialer & Voice Automator</b></p>
  
  [![PyPI version](https://badge.fury.io/py/autodial.svg)](https://badge.fury.io/py/autodial)
  [![Downloads](https://static.pepy.tech/badge/autodial)](https://pepy.tech/project/autodial)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
  [![CI Build](https://github.com/autodial-ai/autodial/actions/workflows/ci.yml/badge.svg)](https://github.com/autodial-ai/autodial/actions)
</div>

<br>

**Autodial** is a production-grade, highly-scalable, self-hosted outbound and inbound phone automation engine. It leverages state-of-the-art Local Speech-to-Text (STT), multi-provider Large Language Models (LLMs), and Local Text-to-Speech (TTS) to create intelligent, human-like phone interactions.

Whether you need a dynamic AI receptionist, a high-volume outbound lead qualifier, or a system to navigate complex IVR menus with DTMF tones, Autodial is the ultimate developer tool. It natively bridges **Twilio** and **Telnyx** media streams with zero friction.

---

## 🚀 Why Autodial?

*   **Multi-LLM Cloud & Local Support**: Power your conversations with **OpenAI**, **Google Gemini**, **MistralAI**, or keep it 100% private and offline using **Ollama**.
*   **Bidirectional Calling**: Trigger automated outbound calls via Python or handle inbound calls instantly by pointing your Twilio/Telnyx webhook to the `/incoming` endpoint.
*   **Provider Agnostic**: Native auto-detection and WebSocket formatting for Twilio and Telnyx. Drop in your API keys and go.
*   **Natural Language CLI**: Execute phone calls from your terminal using plain English (`autodial call bob and ask...`). The CLI automatically extracts parameters using your configured LLM.
*   **Local Transcription Engine**: Powered by `Faster-Whisper` (STT). Optimized for GPU (RTX series) with automatic CPU fallback for lightning-fast voice transcription.
*   **Intelligent Call Termination**: Built-in intent recognition for phrases like "stop calling me" or "goodbye," ensuring polite and immediate hang-ups.
*   **Webhooks & Transcripts**: Every call generates a detailed JSON transcript. Configure a `callback_url` to pipe data directly into your CRM.

---

## 🛠 Quickstart Installation

### Core Requirements
1.  **TTS Engine**: The `piper` binary should be in your system PATH, along with its `.onnx` models.
2.  **LLM Provider**: An API key for OpenAI/Gemini/Mistral, OR a local Ollama instance serving a chat-ready model (e.g., `llama3.2`).
3.  **Telephony**: An active Account SID/API Key, Auth Token, and a verified Phone Number from Twilio or Telnyx.

### Install via PyPI
```bash
pip install autodial
```

---

## ⚙️ Configuration (.env)

Autodial consumes configuration via environment variables. Create a `.env` file in the directory where you run the server:

```env
PORT=8000
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
TWILIO_PHONE_NUMBER=+1234567890

# --- LLM Provider Selection ---
# Options: ollama (default), openai, gemini, mistral
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o

# Cloud API Keys (Required if using cloud provider)
OPENAI_API_KEY=sk-your-key
# GEMINI_API_KEY=AIza...
# MISTRAL_API_KEY=...

# Local Ollama URL (used only if provider is ollama)
OLLAMA_CHAT_URL=http://localhost:11434/api/chat

# --- Local TTS Settings ---
PIPER_MODEL=./en_US-lessac-medium.onnx
```
*(Note: If using Telnyx, provide your Telnyx API keys within the Twilio env vars for drop-in compatibility).*

---

## 🖥 1. Zero-to-One Web GUI

You don't need to manually configure `.env` files or write code to start making calls. Autodial ships with a sleek, native Web Dashboard!

```bash
autodial gui
```

This instantly starts the server and opens `http://localhost:8000` in your browser. From the dashboard, you can:
1. **Configure** your Twilio/Telnyx keys and select your LLM Provider (OpenAI, Gemini, Mistral, Ollama).
2. **Initiate Calls** visually by typing in the target number, context, and goals.
3. **View Transcripts** of your AI's interactive sessions in real-time.

---

## 🗣 2. Natural Language CLI

You don't even need to write Python code to place intelligent calls. Autodial includes a powerful NLP-driven CLI that translates plain English into API actions!

Ensure your Autodial server is running in the background, then simply type:

```bash
autodial call bob at 613-444-0101 and ask how his day is going
```

The CLI uses your configured LLM to instantly extract the target phone number, the conversation context, and the goals, and then dispatches the call automatically.

---

## 🐍 3. Full Python Demo (The API Client)

The library includes a professional `AutodialClient` to make programmatic orchestration seamless.

### `demo.py`
```python
import time
from autodial import AutodialClient

# Connect to your local Autodial server
client = AutodialClient("http://localhost:8000")

def run_outbound_demo():
    print("📞 Placing intelligent outbound call...")
    
    # Scenario: Appointment Reminder with Guardrails
    response = client.dial(
        target_number="+15551234567",
        context="Reminder for Dr. Smith's dental clinic.",
        goals="Confirm the 2:00 PM slot today. Ask if they need directions.",
        system_instructions="Always be polite. If the user is busy, offer to call back later. Keep responses short.",
        callback_url="https://api.yourclinic.com/webhooks/call-results"
    )
    
    print(f"✅ Call Initiated: {response}")

def run_broadcast_demo():
    print("📢 Initiating Mass Broadcast...")
    
    # Scenario: Emergency Alert Broadcast
    response = client.broadcast(
        numbers=["+15550001", "+15550002", "+15550003"],
        message="This is an automated alert from the city. Please evacuate immediately.",
        callback_url="https://api.city.gov/logs"
    )
    
    print(f"✅ Broadcast Initiated: {response}")

if __name__ == "__main__":
    run_outbound_demo()
    time.sleep(5)
    run_broadcast_demo()
```

---

## 📞 4. Handling Inbound Calls (Bidirectional)

Autodial isn't just for outbound dialing. It exposes an `/incoming` REST endpoint that automatically generates the required TwiML/TeXML to connect callers to your AI bot.

**Setup Instructions:**
1. Log in to your Twilio or Telnyx Console.
2. Navigate to your active Phone Number settings.
3. Find the **Webhook URL** for incoming calls.
4. Set it to `POST https://your-autodial-server.com/incoming`

When a user dials your number, the provider hits the endpoint, receives the Media Stream instructions, and the AI answers immediately using your configured `LLM_PROVIDER`.

---

## 📡 API Reference

### `POST /dial`
Initiates a single interactive AI session.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `to_number` | `string` | **Required**. The target phone number in E.164 format. |
| `context` | `string` | Detailed background info for the AI to understand the call's nature. |
| `goals` | `string` | Specific outcomes or data points the AI should strive to achieve. |
| `keywords` | `string` | Focus phrases for the transcription engine to prioritize. |
| `system_instructions` | `string` | High-priority guardrails and behavioral rules for the session. |
| `callback_url` | `string` | POST endpoint to receive the final JSON transcript and status. |

### `POST /incoming`
A webhook endpoint for Twilio/Telnyx. Do not call this manually. It automatically returns `<Connect><Stream .../>` XML to start a bidirectional session.

---

## ⚡ Performance & Benchmarks

Autodial is built for extremely low-latency interactive voice response. When configured with GPU acceleration:

| Component | Pipeline | Typical Latency (End-to-End) |
| :--- | :--- | :--- |
| **STT Engine** | Faster-Whisper (`base.en` / int8 CUDA) | ~150 - 250ms |
| **Intelligence** | Local Ollama (`llama3.2:3b`) | ~300 - 600ms (Time to First Token) |
| **Intelligence** | Cloud (OpenAI `gpt-4o`) | ~400 - 800ms |
| **TTS Engine** | Local Piper TTS (ONNX) | ~50 - 100ms |
| **Total Response Time** | End-of-Speech to Audio Playback | **< 1.0 Second Average** |

*Note: Benchmarks taken on an NVIDIA RTX 3050 Ti Laptop GPU. CPU fallback will add approximately 500-1000ms depending on processor generation.*

---

## 🛡 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

<div align="center">
  <i>Built with ❤️ by the Autodial Maintainers.</i><br>
  <a href="https://github.com/autodial-ai/autodial">GitHub</a> • 
  <a href="https://github.com/autodial-ai/autodial/issues">Issues</a>
</div>
