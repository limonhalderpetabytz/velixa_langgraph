import asyncio
import uuid
from microsoft.teams.api import TypingActivityInput
from microsoft.teams.apps import ActivityContext, App
from config import Config
from langchain_core.messages import HumanMessage
from engineer.engineer_subagent import engineer_subagent
from manager.manager_subagent import manager_subagent
from user.user_subagent import user_subagent
import os
from botbuilder.core.teams import TeamsInfo
from azure.identity import ManagedIdentityCredential


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
    "uday.kiran@petabytz.com": "manager",
    "limon.halder@petabytz.com": "engineer"
}

USER_NAME_USER_EMAIL_MAP={
    "David Miller": "david.miller@petabytz.com",
    "Limon Halder": "limon.halder@petabytz.com",
    "James Anderson": "james.anderson@petabytz.com",
    "Uday Kiran": "uday.kiran@petabytz.com"
}

def get_agent_by_email(email: str) -> str:
    return EMAIL_AGENT_MAP.get(email.lower())

# =====================
# TEAMS APP
# =====================
config = Config()

def create_token_factory():
    def get_token(scopes, tenant_id=None):
        credential = ManagedIdentityCredential(client_id=config.APP_ID)
        if isinstance(scopes, str):
            scopes_list = [scopes]
        else:
            scopes_list = scopes
        token = credential.get_token(*scopes_list)
        return token.token
    return get_token

# Initialize Teams app
app = App(
    token=create_token_factory() if config.APP_TYPE == "UserAssignedMsi" else None
)# Session storage: conversation_id -> subagent + config + history
SESSION_STORE = {}

# Safe send helper
async def safe_send(ctx, text: str):
    if not text:
        text = "(empty message)"
    try:
        await ctx.send(text)
    except Exception as e:
        print(f"Failed to send message: {e}")


# import httpx
# from azure.identity.aio import ClientSecretCredential

# async def get_user_email_by_id(user_id: str):
#     credential = ClientSecretCredential(
#         tenant_id=os.getenv("TENANT_ID"),
#         client_id=os.getenv("CLIENT_ID"),
#         client_secret=os.getenv("CLIENT_SECRET")
#     )
#     token = await credential.get_token("https://graph.microsoft.com/.default")
#     headers = {"Authorization": f"Bearer {token.token}"}
#     url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
#     async with httpx.AsyncClient() as client:
#         resp = await client.get(url, headers=headers)
#         resp.raise_for_status()
#         data = resp.json()
#         return data.get("mail") or data.get("userPrincipalName")


# =====================
# HANDLE INCOMING MESSAGE
# =====================
@app.on_message
async def handle_message(ctx: ActivityContext):
    # Show typing indicator
    await ctx.reply(TypingActivityInput())

    # Use ctx.turn_context and ctx.activity.from_.id
# Use the adapter and activity from the ctx
    # member = await TeamsInfo.get_member(ctx.adapter, ctx.activity)
    # user_name = member.name
    # user_email = member.email or member.user_principal_name

    conversation_id = ctx.activity.conversation.id.strip("/")
    user_input = ctx.activity.text.strip()

    # Get user info directly from activity
    user = ctx.activity.from_
    user_name = getattr(user, "name", "Unknown User")
    user_id = ctx.activity.from_.id
    user_email = USER_NAME_USER_EMAIL_MAP.get(user_name)
    # user_email = "david.miller@petabytz.com"
    # user_name ="David Miller"
    print(f"Received message from {user_name} ({user_email}): {user_input}")

    #user_email = await get_user_email_by_id(user_id)

    #user_email = getattr(user, "user_principal_name", None)
    # if not user_email:
    #     await safe_send(ctx, "Unable to retrieve your email from Teams activity.")
    #     return

    # Step 1: Initialize session if needed
    if conversation_id not in SESSION_STORE:
        agent_type = get_agent_by_email(user_email)
        if not agent_type:
            await safe_send(ctx, "Access denied: No agent assigned to your email.")
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
        #await safe_send(ctx, f"Hello {user_name}, how can I assist you with ServiceNow today?")

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
        await safe_send(ctx, latest_reply)
        # Append agent reply to history
        history.append(messages[-1])

# =====================
# START BOT
# =====================
if __name__ == "__main__":
    print("Starting Teams bot...")
    asyncio.run(app.start())


