import uuid
from langchain_core.messages import HumanMessage
from manager_subagent import manager_subagent  # Import your compiled manager subagent



def run_manager_session():
    """
    Runs an interactive manager session.
    """
    # Generate a unique thread ID for this conversation
    thread_id = uuid.uuid4()

    # Configuration for the agent
    config = {"configurable": {"thread_id": thread_id}}

    print("Manager Interactive Session. Type 'exit' or 'quit' to end.\n")

    while True:
        # Take manager input from terminal
        manager_input = input("Manager: ")

        if manager_input.lower() in ["exit", "quit"]:
            print("Ending session.")
            break

        # Invoke the manager_subagent with the manager's input
        result = manager_subagent.invoke(
            {"messages": [HumanMessage(content=manager_input)]},
            config=config
        )

        # Print all messages returned by the agent
        for message in result.get("messages", []):
            message.pretty_print()


def main():
    run_manager_session()


if __name__ == "__main__":
    main()
