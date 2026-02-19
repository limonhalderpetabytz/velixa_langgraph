from dotenv import load_dotenv # Import function to load environment variables
from langchain_openai import ChatOpenAI # Import the OpenAI chat model
import os

from typing_extensions import TypedDict # For defining dictionaries with type hints
from typing import Annotated, List # For type hinting lists and adding annotations
from langgraph.graph.message import AnyMessage, add_messages # For managing messages in the graph state
from langgraph.managed.is_last_step import RemainingSteps # For tracking recursion limits
from langgraph.checkpoint.memory import MemorySaver # For short-term memory (thread-level state persistence)
from langgraph.store.memory import InMemoryStore # For long-term memory (storing user preferences)
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage

from user_tool import user_tools  # import tools from your user_tools.py
#from user_tool_witout_loging import user_tools  # import tools from your user_tools.py

from langgraph.prebuilt import ToolNode # Pre-built node for executing tools
from user_assist_node import user_assistance # Custom node for user assistance logic

# Load environment variables from the .env file. The `override=True` argument
# ensures that variables from the .env file will overwrite existing environment variables.
load_dotenv(dotenv_path=".env", override=True)

# Initialize the ChatOpenAI model. We're using a specific model from Llama 3.3 series.
# This `model` object will be used throughout the notebook for all LLM interactions.

load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key

llm = ChatOpenAI(model_name="gpt-4", temperature=0)


# Initializing `InMemoryStore` for long-term memory. 
# This store will hold user-specific data like music preferences across sessions.
in_memory_store = InMemoryStore()

# Initializing `MemorySaver` for short-term (thread-level) memory. 
# This checkpointer saves the graph's state after each step, allowing for restarts or interruptions within a thread.
checkpointer = MemorySaver()



class State(TypedDict):
    """Represents the state of our LangGraph agent."""
    # user_id: Stores the unique identifier for the current user.
    user_id: str
    
    # messages: A list of messages that form the conversation history.
    # Annotated with `add_messages` to ensure new messages are appended rather than overwritten.
    messages: Annotated[list[AnyMessage], add_messages]
    
    # loaded_memory: Stores information loaded from the long-term memory store, 
    # typically user preferences or historical context.
    loaded_memory: str
    
    # remaining_steps: Used by LangGraph to track the number of allowed steps 
    # to prevent infinite loops in cyclic graphs.
    remaining_steps: RemainingSteps 


llm_with_user_tools = llm.bind_tools(user_tools)

user_tool_node = ToolNode(user_tools)


# Define a conditional edge function named `should_continue`.
# This function determines the next step in the graph based on the LLM's response.
def should_continue(state: State, config: RunnableConfig):
    # Get the list of messages from the current state.
    messages = state["messages"]
    # Get the last message, which is the response from the `music_assistant` LLM.
    last_message = messages[-1]
    
    # Check if the last message contains any tool calls.
    # LLMs generate `tool_calls` when they decide to use a function.
    if not last_message.tool_calls:
        # If there are no tool calls, it means the LLM has generated a final answer.
        # In this case, the sub-agent's work is done, so we return "end" to signal completion.
        return "end"
    # Otherwise, if there are tool calls,
    else:
        # We need to execute the tool(s). So, we return "continue" to route to the tool execution node.
        return "continue"
    


from langgraph.graph import StateGraph, START, END # Core LangGraph classes and special node names
from utils import show_graph # Utility function to visualize the graph (assumed to be in a utils.py file)

# Initialize a StateGraph with our defined `State` schema.
# This tells LangGraph how the data will flow and be managed within the graph.
user_workflow = StateGraph(State)

# Add the 'user_assistant' node to the graph.
# This node is responsible for the LLM's reasoning and generating tool calls or final responses.
user_workflow.add_node("user_assistant", user_assistance)

# Add the 'user_tool_node' to the graph.
# This node is responsible for executing the tools when requested by the LLM.
user_workflow.add_node("user_tool_node", user_tool_node)


# Define the starting point of the graph.
# All queries will initially enter the 'user_assistant' node.
user_workflow.add_edge(START, "user_assistant")

# Add a conditional edge from 'user_assistant'.
# The `should_continue` function will be called to determine the next node.
user_workflow.add_conditional_edges(
    "user_assistant", # Source node
    should_continue,   # Conditional function to call
    {
        # If `should_continue` returns "continue", route to `user_tool_node`.
        "continue": "user_tool_node",
        # If `should_continue` returns "end", terminate the graph execution.
        "end": END,
    },
)

# Add a normal edge from 'user_tool_node' back to 'user_assistant'.
# After a tool is executed, the result is fed back to the LLM for further reasoning
# or to formulate a final response (ReAct loop).
user_workflow.add_edge("user_tool_node", "user_assistant")

# Compile the graph into a runnable object.
# `name`: A unique identifier for this compiled graph (useful for debugging and logging).
# `checkpointer`: The short-term memory mechanism (MemorySaver) for thread-specific state.
# `store`: The long-term memory mechanism (InMemoryStore) for persistent user data.
user_subagent = user_workflow.compile(name="user_subagent", checkpointer=checkpointer, store = in_memory_store)

# Display a visualization of the compiled graph.
show_graph(user_subagent)






import uuid # Module for generating unique identifiers

# Generate a unique thread ID for this conversation.
# This ensures that the conversation state is isolated and can be resumed later.
thread_id = uuid.uuid4()

# Define the customer's question.
question = "I am facing some issues regarding my camera?"

# Create the configuration dictionary for invoking the graph.
# The `thread_id` is essential for the checkpointer to manage state.
config = {"configurable": {"thread_id": thread_id}}

# Invoke the `user_subagent` with the initial human message and configuration.
# The `invoke` method runs the graph to completion and returns the final state.
result = user_subagent.invoke({"messages": [HumanMessage(content=question)]}, config=config)

# Iterate through the messages in the final state and print them for observation.
# `pretty_print()` provides a formatted output of the message content and role.
for message in result["messages"]:
   message.pretty_print()



