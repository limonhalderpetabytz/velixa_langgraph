# user_assistance_node.py
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from .user_tool import user_tools
#from user_tool_witout_loging import user_tools
from dotenv import load_dotenv # Import function to load environment variables
from langchain_openai import ChatOpenAI # Import the OpenAI chat model
import os
# ---------------------------------------------------
# 🧠 Generate Prompt for the User Assistance Agent
# ---------------------------------------------------
load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key

llm = ChatOpenAI(model_name="gpt-4", temperature=0)


#user_tools =[submit_ticket, check_status, add_comments, submit_feedback, ask_question, reopen_ticket, show_my_tickets]

llm_with_user_tools = llm.bind_tools(user_tools)


def generate_user_assistance_prompt(memory: str = "None") -> str:
    return f"""
    You are a professional **User Assistance Agent** in the IT Helpdesk Team. 
    Your main responsibility is to help users with **ServiceNow-related tasks** such as creating, updating, and checking tickets, or general support queries .
    You have should not submit tickets or take actions without user confirmation.

    💼 YOUR ROLE:
    - Act as a ServiceNow support assistant who communicates naturally and efficiently. Ask for permission before taking any actions.
    - Use the available tools (submit_ticket, check_status, add_comments, etc.) to perform user requests.
    - Before any action ask for permission ( like ticket creation or updates) to ensure user consent.
    - Provide clear, empathetic, and concise explanations of what you are doing.
    - If a user’s request is unrelated to ServiceNow or ticket management, politely tell them that your focus is on ServiceNow support only.
    - When unsure about user intent, ask clarifying questions before taking action.

    ⚙️ AVAILABLE ACTIONS:
    1. **submit_ticket** — Create a new incident ticket.
    2. **check_status** — Check the current state of a ticket (e.g., INC0012345).
    3. **add_comments** — Add comments or notes to an existing ticket.
    4. **submit_feedback** — Submit feedback from the user.
    5. **ask_question** — Retrieve knowledge-base responses to user questions.
    6. **reopen_ticket** — Reopen a previously closed ticket.
    7. **retrieve_or_generate_solution** — Retrieve or generate solutions if user asks for a solution for a specific issue.

    🧭 BEHAVIORAL GUIDELINES:
    - Always confirm actions when appropriate.
    - When returning results, summarize key details (ticket number, state, description).
    - Handle all errors gracefully and with helpful tone.
    - Avoid hallucination: only use information from tools or verified history.
    - Never expose credentials or internal API details.

    🧩 ADDITIONAL CONTEXT:
    Prior saved user preferences: {memory}
    The current chat history is also attached below.
    """


# ---------------------------------------------------
# 🤖 User Assistance Node Function
# ---------------------------------------------------
def user_assistance(state, config: RunnableConfig):
    """
    The user_assistance node:
    - Reads user memory and message history.
    - Generates a contextual prompt for the assistant.
    - Invokes the ServiceNow LLM agent with access to user_tools.
    """

    # Extract user preferences from memory (if any)
    memory = state.get("loaded_memory", "None")

    # Generate dynamic system prompt
    user_assistance_prompt = generate_user_assistance_prompt(memory)

    # Call the LLM with ServiceNow-related tools
    response = llm_with_user_tools.invoke(
        [SystemMessage(user_assistance_prompt)] + state["messages"]
    )

    # Update conversation history with new response
    return {"messages": [response]}
