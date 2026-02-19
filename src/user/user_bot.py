import uuid
from langchain_core.messages import HumanMessage
from .user_subagent import user_subagent  # Import your compiled user subagent



def run_user_session():
    """
    Runs an interactive user Q&A session.
    """
    # Generate a unique thread ID for this conversation
    thread_id = uuid.uuid4()

    # Configuration for the agent
    config = {"configurable": {"thread_id": thread_id}}

    print("Interactive Q&A session. Type 'exit' or 'quit' to end.\n")

    while True:
        # Take user input from terminal
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            print("Ending session.")
            break

        # Invoke the user_subagent with the user's input
        result = user_subagent.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config
        )

        # Print all messages from the agent
        for message in result.get("messages", []):
            message.pretty_print()


def main():
    run_user_session()


if __name__ == "__main__":
    main()
