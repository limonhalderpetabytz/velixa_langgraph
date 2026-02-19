import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from engineer.engineer_subagent import engineer_subagent
from manager.manager_subagent import manager_subagent
from user.user_subagent import user_subagent


# Map agent types to subagents
AGENT_MAP = {
    "engineer": engineer_subagent,
    "manager": manager_subagent,
    "user": user_subagent
}

# Map emails to agent types
EMAIL_AGENT_MAP = {
    "david.miller@petabytz.com": "engineer",
    "bob@example.com": "manager",
    "carol@gmail.com": "user"
}


def get_agent_by_email(email: str) -> str:
    return EMAIL_AGENT_MAP.get(email.lower())

# Store ongoing sessions in memory
SESSIONS = {}

# Request model
class MessageRequest(BaseModel):
    name: str
    email: str
    message: str

app = FastAPI(title="Agent Orchestrator Chat UI")

# Serve static files (optional if you add CSS/JS separately)
#app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def chat_ui():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Agent Chat</title>
        <style>
            body {
                font-family: 'Segoe UI', sans-serif;
                background: #f5f6fa;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 30px;
            }
            h2 {
                color: #333;
                margin-bottom: 10px;
            }
            #chatContainer {
                width: 480px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            #chat {
                padding: 15px;
                height: 420px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .message {
                max-width: 80%;
                padding: 10px 15px;
                border-radius: 15px;
                animation: fadeIn 0.3s ease;
            }
            .user {
                background: #0078ff;
                color: white;
                align-self: flex-end;
                border-bottom-right-radius: 3px;
            }
            .agent {
                background: #e1e1e1;
                color: #333;
                align-self: flex-start;
                border-bottom-left-radius: 3px;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            #inputSection {
                display: flex;
                flex-direction: column;
                padding: 15px;
                border-top: 1px solid #eee;
                background: #fafafa;
            }
            #inputSection input {
                margin: 4px 0;
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 14px;
            }
            #sendSection {
                display: flex;
                margin-top: 6px;
            }
            #userInput {
                flex: 1;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #ccc;
                font-size: 14px;
            }
            button {
                margin-left: 8px;
                background: #0078ff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
                cursor: pointer;
                transition: background 0.2s;
            }
            button:hover {
                background: #005ecb;
            }
            .loading {
                font-style: italic;
                color: #888;
                align-self: center;
                animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
                0% { opacity: 0.3; }
                50% { opacity: 1; }
                100% { opacity: 0.3; }
            }
        </style>
    </head>
    <body>
        <h2>💬 Agent Chat Interface</h2>
        <div id="chatContainer">
            <div id="chat"></div>
            <div id="inputSection">
                <input type="text" id="name" placeholder="Your name" />
                <input type="email" id="email" placeholder="Your email" />
                <div id="sendSection">
                    <input type="text" id="userInput" placeholder="Type a message..." />
                    <button onclick="sendMessage()">Send</button>
                </div>
            </div>
        </div>

        <script>
            const chatDiv = document.getElementById("chat");

            async function sendMessage() {
                const name = document.getElementById("name").value.trim();
                const email = document.getElementById("email").value.trim();
                const message = document.getElementById("userInput").value.trim();
                if (!name || !email || !message) { 
                    alert("Please fill in all fields.");
                    return; 
                }

                appendMessage("You", message, "user");
                document.getElementById("userInput").value = "";

                // Add loading indicator
                const loader = document.createElement("div");
                loader.classList.add("loading");
                loader.innerText = "Agent is typing...";
                chatDiv.appendChild(loader);
                chatDiv.scrollTop = chatDiv.scrollHeight;

                try {
                    const response = await fetch("/send_message/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ name, email, message })
                    });

                    const data = await response.json();
                    loader.remove();

                    if (data.messages && data.messages.length > 0) {
                        data.messages.forEach(msg => appendMessage("Agent", msg, "agent"));
                    } else {
                        appendMessage("System", "No response received.", "agent");
                    }
                } catch (err) {
                    loader.remove();
                    appendMessage("Error", "Connection error. Try again later.", "agent");
                }

                chatDiv.scrollTop = chatDiv.scrollHeight;
            }

            function appendMessage(sender, text, cls) {
                const msgDiv = document.createElement("div");
                msgDiv.classList.add("message", cls);
                msgDiv.innerHTML = `<b>${sender}:</b> ${text}`;
                chatDiv.appendChild(msgDiv);
                chatDiv.scrollTop = chatDiv.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/send_message/")
def send_message(req: MessageRequest):
    agent_type = get_agent_by_email(req.email)
    if not agent_type:
        raise HTTPException(status_code=403, detail="No agent assigned for this email.")

    # Retrieve or create session
    if req.email not in SESSIONS:
        thread_id = uuid.uuid4()
        SESSIONS[req.email] = {
            "agent_type": agent_type,
            "thread_id": thread_id,
            "subagent": AGENT_MAP[agent_type]
        }
        # Initial message to agent with email
        initial_message = f"User name: {req.name} User email: {req.email}"
        _ = SESSIONS[req.email]["subagent"].invoke(
            {"messages": [HumanMessage(content=initial_message)]},
            config={"configurable": {"thread_id": thread_id}}
        )

    # Send user message to agent
    thread_id = SESSIONS[req.email]["thread_id"]
    subagent = SESSIONS[req.email]["subagent"]
    response = subagent.invoke(
        {"messages": [HumanMessage(content=req.message)]},
        config={"configurable": {"thread_id": thread_id}}
    )

    messages = [msg.content for msg in response.get("messages", [])]
    return {"messages": messages}


@app.post("/end_session/")
def end_session(email: str):
    if email in SESSIONS:
        del SESSIONS[email]
        return {"status": "Session ended."}
    return {"status": "No session found for this email."}

