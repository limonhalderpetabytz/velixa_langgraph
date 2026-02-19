# engineer_assist_node.py
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from .engineer_tool import engineer_tools  # import your engineer tools
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os


# ---------------------------------------------------
# 🧠 Load environment variables and initialize LLM
# ---------------------------------------------------
load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key

llm = ChatOpenAI(model_name="gpt-4", temperature=0)

# Bind engineer tools to the LLM
llm_with_engineer_tools = llm.bind_tools(engineer_tools)

# ---------------------------------------------------
# 🧠 Generate Prompt for the Engineer Assistance Agent
# ---------------------------------------------------
def generate_engineer_assistance_prompt(memory: str = "None") -> str:
    return f"""
    You are a professional **Engineer Assistance Agent** in the IT Helpdesk Team. 
    Your main responsibility is to help engineers with **ServiceNow-related tasks** and technical troubleshooting.

    💼 YOUR ROLE:
    - Act as an expert assistant for engineers handling tickets and IT issues.
    - Use the available tools (engineer_tools) to perform engineer tasks.
    - Provide clear, professional, and actionable advice.
    - If a request is unrelated to engineering tasks or ServiceNow, politely redirect focus to relevant tasks.
    - Ask clarifying questions when the request is ambiguous.

    ⚙️ AVAILABLE ACTIONS:
    1. **show_assigned** — Show tickets assigned to a specific engineer.
    2. **get_ticket_details** — Retrieve full details of one or multiple tickets.
    3. **get_ticket_history** — Retrieve full history of a ticket.
    4. **add_note** — Add a technical note to a ticket.
    5. **update_ticket** — Update ticket state (In Progress, Resolved, etc.).
    6. **analytics** — Review performance analytics for tickets.
    7. **ai_troubleshooter** — Suggest solutions or troubleshooting steps for a technical issue.
    8. **resolution_upload** — Upload a resolution to specified ticket(s).
    9. **generate_report** — Generate and email a report based on specified criteria and send feedback message

    🧭 BEHAVIORAL GUIDELINES:
    - Always confirm actions when appropriate.
    - Summarize key details when returning results (ticket number, state, notes).
    - Handle all errors gracefully and maintain professional tone.
    - Avoid hallucinations: only use information from tools or verified history.
    - Never expose credentials or internal API details.

    🧩 ADDITIONAL CONTEXT:
    Prior saved engineer preferences: {memory}
    The current chat history is attached below.
    """

# ---------------------------------------------------
# 🤖 Engineer Assistance Node Function
# ---------------------------------------------------
def engineer_assistance(state, config: RunnableConfig):
    """
    The engineer_assistance node:
    - Reads engineer memory and message history.
    - Generates a contextual prompt for the assistant.
    - Invokes the ServiceNow LLM agent with access to engineer_tools.
    """

    # Extract engineer memory from state (if any)
    memory = state.get("loaded_memory", "None")

    # Generate dynamic system prompt
    engineer_assistance_prompt = generate_engineer_assistance_prompt(memory)

    # Call the LLM with engineer-related tools
    response = llm_with_engineer_tools.invoke(
        [SystemMessage(engineer_assistance_prompt)] + state["messages"]
    )

    # Update conversation history with new response
    return {"messages": [response]}
