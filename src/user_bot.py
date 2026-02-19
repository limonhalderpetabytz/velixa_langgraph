import uuid
from langchain.schema import HumanMessage
from usrer_subagent import user_subagent

# Generate a unique thread ID for this conversation
thread_id = uuid.uuid4()

# Configuration for the graph
config = {"configurable": {"thread_id": thread_id}}

print("Interactive Q&A session. Type 'exit' to quit.\n")

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
    for message in result["messages"]:
        message.pretty_print()

