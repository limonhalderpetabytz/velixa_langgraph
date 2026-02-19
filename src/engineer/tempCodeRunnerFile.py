import uuid
from langchain_core.messages import HumanMessage
from engineer_subagent import engineer_subagent  # Import your compiled engineer subagent

# Generate a unique thread ID for this conversation
thread_id = uuid.uuid4()

# Configuration for the graph
config = {"configurable": {"thread_id": thread_id}}

print("Engineer Interactive Session. Type 'exit' to quit.\n")


while True:
    # Take engineer input from terminal
    engineer_input = input("Engineer: ")
    
    if engineer_input.lower() in ["exit", "quit"]:
        print("Ending session.")
        break
    
    # Invoke the engineer_subagent with the engineer's input
    result = engineer_subagent.invoke(
        {"messages": [HumanMessage(content=engineer_input)]},
        config=config
    )
    
    # Print all messages returned by the agent
    for message in result["messages"]:
        message.pretty_print()
