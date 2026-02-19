import uuid
from langchain_core.messages import HumanMessage
from engineer.engineer_subagent import engineer_subagent
from manager.manager_subagent import manager_subagent
from user.user_subagent import user_subagent

# Map agent types to their corresponding subagents
AGENT_MAP = {
    "engineer": engineer_subagent,
    "manager": manager_subagent,
    "user": user_subagent
}

# Map emails to agent types
EMAIL_AGENT_MAP = {
    "david.miller@petabytz.com": "engineer",
    "bob@example.com": "manager",
    "carol@example.com": "user"
}

def get_agent_by_email(email: str) -> str:
    return EMAIL_AGENT_MAP.get(email.lower())

def run_session(agent_type: str, user_name: str, user_email: str):
    """
    Runs an interactive session for the specified agent_type.
    The agent receives the user's email immediately.
    """
    subagent = AGENT_MAP[agent_type]

    # Generate a unique thread ID for this session
    thread_id = uuid.uuid4()
    config = {"configurable": {"thread_id": thread_id}}

    # First message to agent: provide user's email
    initial_message = f" User name: {user_name} User email: {user_email} "
    result = subagent.invoke(
        {"messages": [HumanMessage(content=initial_message)]},
        config=config
    )

    # Print agent response to email
    for message in result.get("messages", []):
        message.pretty_print()

    print(f"\nConnected to {agent_type} agent. Type 'exit' or 'quit' to end the session.\n")

    # Continue interactive session
    while True:
        user_input = input(f"{agent_type.capitalize()}: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Ending session.")
            break

        result = subagent.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config
        )
        for message in result.get("messages", []):
            message.pretty_print()

def main():
    print("=== Login ===")
    name = input("Enter your name: ").strip()
    email = input("Enter your email: ").strip()
    agent_type = get_agent_by_email(email)

    if not agent_type:
        print("No agent assigned for this email. Access denied.")
        return

    # Directly start session and pass email to agent
    run_session(agent_type,name,email)

if __name__ == "__main__":
    main()


