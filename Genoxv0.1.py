# genox_v0.1.py
from flask import Flask, request, jsonify, render_template_string
import google.generativeai as genai
import os
import re
from datetime import datetime, timedelta
from collections import deque

app = Flask(__name__)
genai.configure(api_key=os.getenv("G_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash-lite')

# Rate limiting tracking
request_log = deque(maxlen=25)
token_count = 0
daily_requests = 0

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Genox V0.1</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root {
            --bg-dark: #1a1a1a;
            --bg-darker: #121212;
            --accent: #2a2a2a;
            --text-primary: #e0e0e0;
            --text-secondary: #888;
            --primary: #007bff;
            --input-bg: #2d2d2d;
        }
        
        body {
            margin: 0;
            font-family: 'Segoe UI', system-ui;
            background: var(--bg-dark);
            color: var(--text-primary);
            display: flex;
            min-height: 100vh;
            flex-direction: column;
        }

        .sidebar {
            width: 300px;
            background: var(--bg-darker);
            padding: 20px;
            border-right: 1px solid #333;
            position: fixed;
            height: calc(100% - 80px);
            transition: transform 0.3s ease;
            z-index: 100;
            overflow-y: auto;
            top: 0;
        }

        .sidebar-toggle {
            display: none;
            position: fixed;
            left: 10px;
            top: 10px;
            z-index: 101;
            background: var(--primary);
            border: none;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1.2rem;
        }

        .monitor-card {
            background: var(--accent);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }

        .monitor-value {
            font-size: 24px;
            font-weight: 600;
            color: var(--primary);
        }

        .monitor-label {
            color: var(--text-secondary);
            font-size: 14px;
            margin-bottom: 8px;
        }

        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            margin-left: 300px;
            transition: margin 0.3s ease;
            padding-bottom: 80px;
        }

        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }

        .message {
            margin: 15px 0;
            padding: 15px 20px;
            border-radius: 12px;
            max-width: 85%;
            background: var(--accent);
            word-break: break-word;
            line-height: 1.6;
        }

        .user-message {
            background: var(--primary);
            margin-left: auto;
            margin-right: 0;
        }

        .bot-message {
            margin-left: 0;
            margin-right: auto;
            width: fit-content;
        }

        .bot-message strong {
            color: var(--primary);
            font-weight: 600;
        }

        .input-container {
            padding: 20px;
            background: var(--bg-darker);
            display: flex;
            gap: 10px;
            position: fixed;
            bottom: 0;
            right: 0;
            left: 300px;
            z-index: 102;
            transition: left 0.3s ease;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.2);
        }

        input {
            flex: 1;
            padding: 12px;
            background: var(--input-bg);
            border: none;
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 16px;
            transition: all 0.3s ease;
        }

        input::placeholder {
            color: var(--text-secondary);
        }

        button {
            padding: 12px 24px;
            background: var(--primary);
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            transition: opacity 0.2s;
            font-size: 16px;
        }

        .token-limits {
            margin-top: 20px;
            padding: 15px;
            background: var(--accent);
            border-radius: 8px;
        }

        .version-info {
            margin-top: 15px;
            padding: 15px;
            background: var(--accent);
            border-radius: 8px;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.9em;
        }

        @media (max-width: 768px) {
            .sidebar {
                transform: translateX(-100%);
                height: 100%;
            }

            .sidebar.active {
                transform: translateX(0);
            }

            .chat-container {
                margin-left: 0;
                width: 100%;
                padding-bottom: 0;
            }

            .input-container {
                left: 0;
            }

            .sidebar-toggle {
                display: block;
            }

            .message {
                max-width: 90%;
                font-size: 14px;
                margin: 12px 0;
            }

            .monitor-card {
                padding: 12px;
            }

            .monitor-value {
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <button class="sidebar-toggle" onclick="toggleSidebar()">☰</button>
    
    <div class="sidebar" id="sidebar">
        <h2>Genox V0.1</h2>
        
        <div class="monitor-card">
            <div class="monitor-label">Requests/Minute</div>
            <div class="monitor-value" id="rpm">0/25</div>
        </div>

        <div class="monitor-card">
            <div class="monitor-label">Tokens/Minute</div>
            <div class="monitor-value" id="tpm">0/1M</div>
        </div>

        <div class="monitor-card">
            <div class="monitor-label">Daily Requests</div>
            <div class="monitor-value" id="daily">0/1450</div>
        </div>

        <div class="token-limits">
            <div style="margin-bottom: 10px; color: var(--primary);">Token Limits:</div>
            <div>Input: 1,000 tokens</div>
            <div>Output: 1,000 tokens</div>
        </div>

        <div class="version-info">
            <div>Genox v0.1</div>
            <div>© 2024 All rights reserved</div>
        </div>
    </div>

    <div class="chat-container">
        <div class="chat-messages" id="chat"></div>
        <div class="input-container">
            <input type="text" id="input" placeholder="Type your message..." 
                   maxlength="4000" autocomplete="off">
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sidebar = document.getElementById('sidebar');

        function toggleSidebar() {
            sidebar.classList.toggle('active');
        }

        function addMessage(text, isUser) {
            const msg = document.createElement('div');
            msg.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
            msg.innerHTML = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            chat.appendChild(msg);
            chat.scrollTop = chat.scrollHeight;
        }

        async function sendMessage() {
            const message = input.value.trim();
            if (!message) return;

            const btn = document.querySelector('button');
            btn.disabled = true;
            input.value = '';
            input.placeholder = 'AI is typing...';
            input.disabled = true;
            addMessage(message, true);

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message})
                });

                const data = await response.json();
                
                if (data.message) {
                    addMessage(data.message, false);
                    updateMetrics(data.usage);
                } else {
                    addMessage(`Error: ${data.error || 'Unknown error'}`, false);
                }
            } catch (error) {
                addMessage(`Error: ${error.message}`, false);
            } finally {
                input.placeholder = 'Type your message...';
                input.disabled = false;
                btn.disabled = false;
                input.focus();
            }
        }

        function updateMetrics(usage) {
            if (!usage) return;
            
            document.getElementById('rpm').textContent = 
                `${usage.current_rpm}/${usage.max_rpm}`;
            
            document.getElementById('tpm').textContent = 
                `${Math.round(usage.tpm / 1000)}K/${usage.max_tpm / 1000000}M`;
            
            document.getElementById('daily').textContent = 
                `${usage.daily_requests}/${usage.daily_limit}`;
        }

        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && 
                !sidebar.contains(e.target) && 
                !e.target.classList.contains('sidebar-toggle')) {
                sidebar.classList.remove('active');
            }
        });

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    global request_log, token_count, daily_requests
    
    try:
        # Rate limiting checks
        now = datetime.now()
        request_log.append(now)
        
        # Calculate RPM
        recent_requests = [t for t in request_log if t > now - timedelta(minutes=1)]
        if len(recent_requests) >= 25:
            return jsonify({'error': 'Rate limit exceeded: 25 requests/minute'}), 429

        # Get and truncate input
        data = request.get_json()
        input_text = data['message'][:4000]  # 1000 tokens @ 4 chars/token

        # Generate response with strict token limits
        response = model.generate_content(
            input_text,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=1000,
                temperature=0.7
            )
        )
        
        output_text = response.text

        # Token estimation (4 characters = 1 token)
        input_tokens = len(input_text) // 4
        output_tokens = len(output_text) // 4
        token_count += input_tokens + output_tokens
        daily_requests += 1

        # Format response
        formatted_response = re.sub(
            r'\b(AI|machine learning|neural networks|algorithm|model|training|data)\b',
            r'**\1**',
            output_text,
            flags=re.IGNORECASE
        )
        
        return jsonify({
            'message': formatted_response,
            'usage': {
                'current_rpm': len(recent_requests),
                'max_rpm': 25,
                'tpm': token_count,
                'max_tpm': 1000000,
                'daily_requests': daily_requests,
                'daily_limit': 1450
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)