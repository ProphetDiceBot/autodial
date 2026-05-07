def get_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autodial Dashboard</title>
    <style>
        :root {
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
            --success: #10b981;
            --danger: #ef4444;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, sans-serif;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            display: flex;
            height: 100vh;
        }

        /* Sidebar */
        .sidebar {
            width: 250px;
            background: var(--bg-card);
            border-right: 1px solid var(--border);
            padding: 2rem 1rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .sidebar h2 {
            font-size: 1.5rem;
            color: var(--primary);
            text-align: center;
            margin-bottom: 2rem;
            letter-spacing: 1px;
        }

        .nav-btn {
            background: transparent;
            color: var(--text-muted);
            border: none;
            padding: 1rem;
            text-align: left;
            font-size: 1rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 600;
        }

        .nav-btn:hover {
            background: rgba(59, 130, 246, 0.1);
            color: var(--primary);
        }

        .nav-btn.active {
            background: var(--primary);
            color: white;
        }

        /* Main Content */
        .main-content {
            flex: 1;
            padding: 3rem;
            overflow-y: auto;
        }

        .tab-content {
            display: none;
            animation: fadeIn 0.3s;
        }

        .tab-content.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        h1 {
            margin-bottom: 2rem;
            font-size: 2rem;
        }

        .card {
            background: var(--bg-card);
            padding: 2rem;
            border-radius: 12px;
            border: 1px solid var(--border);
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--text-muted);
            font-size: 0.9rem;
            font-weight: 500;
        }

        input, select, textarea {
            width: 100%;
            padding: 0.75rem 1rem;
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: white;
            font-size: 1rem;
            transition: border-color 0.2s;
        }

        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--primary);
        }

        textarea {
            resize: vertical;
            min-height: 100px;
        }

        button.primary {
            background: var(--primary);
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: background 0.2s;
        }

        button.primary:hover {
            background: var(--primary-hover);
        }

        /* Logs List */
        .log-item {
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        .log-meta {
            display: flex;
            justify-content: space-between;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
        }

        .msg-user { color: #60a5fa; margin: 0.25rem 0;}
        .msg-assistant { color: #10b981; margin: 0.25rem 0;}
        .msg-system { color: #f59e0b; margin: 0.25rem 0;}

        /* Notification */
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 2rem;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            transform: translateX(150%);
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 1000;
        }
        .notify-success { background: var(--success); }
        .notify-error { background: var(--danger); }
        .notification.show { transform: translateX(0); }

    </style>
</head>
<body>

    <div class="sidebar">
        <h2>📞 Autodial</h2>
        <button class="nav-btn active" onclick="switchTab('dialer')">Dialer</button>
        <button class="nav-btn" onclick="switchTab('logs'); fetchLogs();">Call Logs</button>
        <button class="nav-btn" onclick="switchTab('settings'); fetchConfig();">Settings</button>
    </div>

    <div class="main-content">
        <!-- Dialer Tab -->
        <div id="dialer" class="tab-content active">
            <h1>Launch Outbound Call</h1>
            <div class="card">
                <form id="dialForm" onsubmit="event.preventDefault(); placeCall();">
                    <div class="form-group">
                        <label>Target Phone Number (E.164 Format)</label>
                        <input type="text" id="to_number" placeholder="+15551234567" required>
                    </div>
                    <div class="form-group">
                        <label>Context (Who are you calling?)</label>
                        <textarea id="context" placeholder="You are calling John to remind him about his dentist appointment."></textarea>
                    </div>
                    <div class="form-group">
                        <label>Goals (What should the AI achieve?)</label>
                        <textarea id="goals" placeholder="Confirm the 2PM slot and ask if they need directions."></textarea>
                    </div>
                    <div class="form-group">
                        <label>System Instructions (Guardrails)</label>
                        <textarea id="system_instructions" placeholder="Always be polite. If they are busy, offer to call back."></textarea>
                    </div>
                    <button type="submit" class="primary" id="dialBtn">Initiate Call Sequence</button>
                </form>
            </div>
        </div>

        <!-- Logs Tab -->
        <div id="logs" class="tab-content">
            <h1>Recent Call Transcripts</h1>
            <button class="primary" onclick="fetchLogs()" style="width: auto; margin-bottom: 2rem;">Refresh Logs</button>
            <div id="logsContainer"></div>
        </div>

        <!-- Settings Tab -->
        <div id="settings" class="tab-content">
            <h1>Engine Configuration</h1>
            <div class="card">
                <form id="settingsForm" onsubmit="event.preventDefault(); saveConfig();">
                    <h3 style="margin-bottom: 1rem; color: var(--primary);">Telephony (Twilio / Telnyx)</h3>
                    <div class="form-group">
                        <label>Account SID / API Key</label>
                        <input type="text" id="cfg_twilio_sid" placeholder="AC...">
                    </div>
                    <div class="form-group">
                        <label>Auth Token</label>
                        <input type="password" id="cfg_twilio_token" placeholder="••••••••">
                    </div>
                    <div class="form-group">
                        <label>Outbound Phone Number</label>
                        <input type="text" id="cfg_twilio_number" placeholder="+1234567890">
                    </div>

                    <h3 style="margin: 2rem 0 1rem; color: var(--primary);">Intelligence (LLM)</h3>
                    <div class="form-group">
                        <label>LLM Provider</label>
                        <select id="cfg_llm_provider" onchange="toggleProviderFields()">
                            <option value="ollama">Local: Ollama</option>
                            <option value="openai">Cloud: OpenAI</option>
                            <option value="gemini">Cloud: Google Gemini</option>
                            <option value="mistral">Cloud: MistralAI</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Model Name</label>
                        <input type="text" id="cfg_llm_model" placeholder="llama3.2:3b / gpt-4o / gemini-1.5-flash">
                    </div>
                    
                    <div id="field_ollama" class="form-group">
                        <label>Ollama Chat URL</label>
                        <input type="text" id="cfg_ollama_url" placeholder="http://localhost:11434/api/chat">
                    </div>
                    <div id="field_openai" class="form-group" style="display:none;">
                        <label>OpenAI API Key</label>
                        <input type="password" id="cfg_openai_key" placeholder="sk-...">
                    </div>
                    <div id="field_gemini" class="form-group" style="display:none;">
                        <label>Gemini API Key</label>
                        <input type="password" id="cfg_gemini_key" placeholder="AIza...">
                    </div>
                    <div id="field_mistral" class="form-group" style="display:none;">
                        <label>Mistral API Key</label>
                        <input type="password" id="cfg_mistral_key" placeholder="...">
                    </div>

                    <button type="submit" class="primary" style="margin-top: 1rem;">Save & Apply Configuration</button>
                </form>
            </div>
        </div>
    </div>

    <!-- Notification Toast -->
    <div id="toast" class="notification"></div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }

        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = `notification notify-${type} show`;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        function toggleProviderFields() {
            const provider = document.getElementById('cfg_llm_provider').value;
            document.getElementById('field_ollama').style.display = (provider === 'ollama') ? 'block' : 'none';
            document.getElementById('field_openai').style.display = (provider === 'openai') ? 'block' : 'none';
            document.getElementById('field_gemini').style.display = (provider === 'gemini') ? 'block' : 'none';
            document.getElementById('field_mistral').style.display = (provider === 'mistral') ? 'block' : 'none';
        }

        async function fetchConfig() {
            try {
                const res = await fetch('/api/config');
                const data = await res.json();
                document.getElementById('cfg_twilio_sid').value = data.TWILIO_ACCOUNT_SID || '';
                document.getElementById('cfg_twilio_token').value = data.TWILIO_AUTH_TOKEN || '';
                document.getElementById('cfg_twilio_number').value = data.TWILIO_PHONE_NUMBER || '';
                
                document.getElementById('cfg_llm_provider').value = data.LLM_PROVIDER || 'ollama';
                document.getElementById('cfg_llm_model').value = data.LLM_MODEL || '';
                
                document.getElementById('cfg_ollama_url').value = data.OLLAMA_CHAT_URL || '';
                document.getElementById('cfg_openai_key').value = data.OPENAI_API_KEY || '';
                document.getElementById('cfg_gemini_key').value = data.GEMINI_API_KEY || '';
                document.getElementById('cfg_mistral_key').value = data.MISTRAL_API_KEY || '';
                
                toggleProviderFields();
            } catch (e) {
                console.error(e);
            }
        }

        async function saveConfig() {
            const payload = {
                TWILIO_ACCOUNT_SID: document.getElementById('cfg_twilio_sid').value,
                TWILIO_AUTH_TOKEN: document.getElementById('cfg_twilio_token').value,
                TWILIO_PHONE_NUMBER: document.getElementById('cfg_twilio_number').value,
                LLM_PROVIDER: document.getElementById('cfg_llm_provider').value,
                LLM_MODEL: document.getElementById('cfg_llm_model').value,
                OLLAMA_CHAT_URL: document.getElementById('cfg_ollama_url').value,
                OPENAI_API_KEY: document.getElementById('cfg_openai_key').value,
                GEMINI_API_KEY: document.getElementById('cfg_gemini_key').value,
                MISTRAL_API_KEY: document.getElementById('cfg_mistral_key').value,
            };

            try {
                const res = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                if(res.ok) {
                    showToast('Configuration saved successfully!');
                } else {
                    showToast('Failed to save config', 'error');
                }
            } catch (e) {
                showToast('Network error', 'error');
            }
        }

        async function placeCall() {
            const btn = document.getElementById('dialBtn');
            btn.textContent = "Initiating...";
            btn.disabled = true;

            const payload = {
                to_number: document.getElementById('to_number').value,
                context: document.getElementById('context').value,
                goals: document.getElementById('goals').value,
                system_instructions: document.getElementById('system_instructions').value,
            };

            try {
                const res = await fetch('/dial', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                if(res.ok) {
                    showToast('Call dispatched to target!');
                } else {
                    const err = await res.text();
                    showToast('Call failed: ' + err, 'error');
                }
            } catch (e) {
                showToast('Network error while dialing', 'error');
            }

            btn.textContent = "Initiate Call Sequence";
            btn.disabled = false;
        }

        async function fetchLogs() {
            const container = document.getElementById('logsContainer');
            container.innerHTML = '<p>Loading logs...</p>';
            try {
                const res = await fetch('/api/logs');
                const logs = await res.json();
                
                if (logs.length === 0) {
                    container.innerHTML = '<p style="color: var(--text-muted)">No call logs found yet.</p>';
                    return;
                }

                container.innerHTML = logs.map(log => {
                    const messages = log.transcript.map(t => {
                        let cls = '';
                        if(t.role === 'user') cls = 'msg-user';
                        else if(t.role === 'assistant') cls = 'msg-assistant';
                        else cls = 'msg-system';
                        return `<div class="${cls}"><b>[${t.role.toUpperCase()}]</b>: ${t.content}</div>`;
                    }).join('');

                    return `
                    <div class="log-item">
                        <div class="log-meta">
                            <span>Call SID: ${log.call_sid}</span>
                            <span>Stream: ${log.stream_sid}</span>
                        </div>
                        <div style="margin-top: 10px; font-family: monospace; font-size: 0.9rem;">
                            ${messages}
                        </div>
                    </div>
                    `;
                }).join('');
            } catch (e) {
                container.innerHTML = '<p style="color: var(--danger)">Failed to load logs.</p>';
            }
        }
    </script>
</body>
</html>
"""
