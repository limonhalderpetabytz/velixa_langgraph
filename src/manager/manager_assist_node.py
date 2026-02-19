# manager_assist_node.py
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from .manager_tool import manager_tools  # import your manager tools
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv(dotenv_path=".env", override=True)

# Initialize LLM
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key
llm = ChatOpenAI(model_name="gpt-4", temperature=0)

# Bind all manager tools to the LLM
llm_with_manager_tools = llm.bind_tools(manager_tools)

# -----------------------------
# Generate Manager Prompt
# -----------------------------
def generate_manager_prompt(memory: str = "None") -> str:
    return f"""
You are a professional **Manager Assistance Agent** in the IT Helpdesk Team.
Your responsibilities include helping managers monitor tickets, generate reports, and guide team performance.

💼 ROLE:
- Assist managers with ServiceNow-related tasks.
- Use available tools to fetch tickets, show details, and generate incident reports.
- Provide actionable advice and summaries.
- Politely redirect unrelated requests.

⚙️ AVAILABLE ACTIONS:
1. show_tickets — Show top open tickets.
2. fetch_individual_ticket — Get details of a specific ticket.
3. show_individual_ticket — Show formatted view of a ticket.
4. fetch_recent_incidents — Fetch recent incidents for reporting.

🧭 GUIDELINES:
- Summarize key details (ticket number, state, SLA, age).
- Handle errors gracefully.
- Avoid hallucinations; only use tool outputs.
- Never expose credentials.

📌 Prior saved manager preferences: {memory}
"""

# -----------------------------
# Manager Assistance Node
# -----------------------------
def manager_assistance(state, config: RunnableConfig):
    """
    Manager Assistance Node:
    - Reads manager memory and chat history.
    - Generates a contextual prompt.
    - Invokes the LLM bound with manager tools.
    """
    memory = state.get("loaded_memory", "None")
    manager_prompt = generate_manager_prompt(memory)
    messages = [SystemMessage(manager_prompt)] + state.get("messages", [])

    # Call LLM with bound tools
    response = llm_with_manager_tools.invoke(messages)

    # Update conversation history
    return {"messages": [response]}
