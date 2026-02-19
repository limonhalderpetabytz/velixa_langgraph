import asyncio
import uuid
import os
from botbuilder.core import TurnContext
from botbuilder.core.teams import TeamsInfo
from botbuilder.schema import Activity, ActivityTypes
from azure.identity.aio import ClientSecretCredential
import httpx

from config import Config
from langchain_core.messages import HumanMessage
from engineer.engineer_subagent import engineer_subagent
from manager.manager_subagent import manager_subagent
from user.user_subagent import user_subagent

# =====================
# CONFIGURATION
# =====================
config = Config()

AGENT_MAP = {
    "engineer": engineer_subagent,
    "manager": manager_subagent,
    "user": user_subagent
}

EMAIL_AGENT_MAP = {
    "david.miller@petabytz.com": "engineer",
    "bob@example.com": "manager",
    "limon.halder@petabytz.com": "user"
}

def get_agent_by_email(email: str) -> str:
    return EMAIL_AGENT_MAP.get(email.lower())

# =====================
# SESSION STORE
# =====================
SESSION_STORE = {}  # conversation_id -> subagent + config + history

# =====================
# SAFE SEND HELPER
# =====================
async def safe_send(turn_context: TurnContext, text: str):
    if not text:
        text = "(empty message)"
    try:
        await turn_context.send_activity(Activity(type=ActivityTypes.message, text=text))
    except Exception as e:
        print(f"Failed to send message: {e}")

# =====================
# GET USER EMAIL
# =====================
async def get_user_email_by_id(user_id: str):
    credential = ClientSecretCredential(
        tenant_id=os.getenv("TENANT_ID"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET")
    )
    token = await credential.get_token("https://graph.microsoft.com/.default")
    headers = {"Authorization": f"Bearer {token.token}"}
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("mail") or data.get("userPrincipalName")

# =====================
# HANDLE INCOMING MESSAGE
# =====================
async def handle_message(turn_context: TurnContext):
    # Show typing indicator
    typing_activity = Activity(type=ActivityTypes.typing)
    await turn_context.send_activity(typing_activity)

    activity = turn_context.activity
    conversation_id = activity.conversation.id.strip("/")
    user_input = (activity.text or "").strip()

    # Get user info from activity
    user = activity.from_property
    user_name = getattr(user, "name", "Unknown User")
    user_id = getattr(user, "id", None)
    user_email = getattr(user, "user_principal_name", None)
    
    # Optional: fetch email from Graph API if not available
    if not user_email and user_id:
        user_email = await get_user_email_by_id(user_id)

    if not user_email:
        await safe_send(turn_context, "Unable to retrieve your email from Teams activity.")
        return

    # Step 1: Initialize session if needed
    if conversation_id not in SESSION_STORE:
        agent_type = get_agent_by_email(user_email)
        if not agent_type:
            await safe_send(turn_context, "Access denied: No agent assigned to your email.")
            return

        subagent = AGENT_MAP[agent_type]
        thread_id = uuid.uuid4()
        config_session = {"configurable": {"thread_id": thread_id}}

        # Initialize history with user info
        history = [HumanMessage(content=f"User name: {user_name}, User email: {user_email}")]

        SESSION_STORE[conversation_id] = {
            "subagent": subagent,
            "config": config_session,
            "history": history
        }

        # Send initial greeting
        await safe_send(turn_context, f"Hello {user_name}, how can I assist you with ServiceNow today?")

    # Step 2: Continue session
    session = SESSION_STORE[conversation_id]
    subagent = session["subagent"]
    config_session = session["config"]
    history = session["history"]

    # Append latest user message to history
    history.append(HumanMessage(content=user_input))

    # Invoke agent with full history
    result = subagent.invoke(
        {"messages": history},
        config=config_session
    )

    # Send only the last message from agent
    messages = result.get("messages", [])
    if messages:
        latest_reply = messages[-1].content
        await safe_send(turn_context, latest_reply)
        # Append agent reply to history
        history.append(messages[-1])

# =====================
# BOT RUNNER (Example)
# =====================
# This assumes you integrate handle_message with your BotFramework Adapter:
# Example:
# await adapter.process_activity(req, auth_header, handle_message)
