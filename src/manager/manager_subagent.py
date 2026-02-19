# engineer_subagent.py
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os
import uuid

# import sys
# import os
# sys.path.append(os.path.dirname(__file__))  # add current folder to path
# from utils import show_graph

from typing_extensions import TypedDict
from typing import Annotated, List
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.managed.is_last_step import RemainingSteps
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
#from manager_subagent import manager_subagent  # Import your compiled manager subagent

from utils import show_graph

# Import your manager tools
from .manager_tool import manager_tools
from .manager_assist_node import manager_assistance  # similar to user_assistance but for managers

# -------------------------------------------------------------------
# 1️⃣ Load environment and initialize LLM
# -------------------------------------------------------------------

load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key

llm = ChatOpenAI(model_name="gpt-4", temperature=0)


# -------------------------------------------------------------------
# 2️⃣ Initialize memory systems
# -------------------------------------------------------------------
in_memory_store = InMemoryStore()
checkpointer = MemorySaver()

# -------------------------------------------------------------------
# 3️⃣ Define the state schema
# -------------------------------------------------------------------
class ManagerState(TypedDict):
    """Represents the state of the manager subagent."""
    manager_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    loaded_memory: str
    remaining_steps: RemainingSteps

# -------------------------------------------------------------------
# 4️⃣ Bind tools and create a tool node
# -------------------------------------------------------------------
llm_with_manager_tools = llm.bind_tools(manager_tools)
manager_tool_node = ToolNode(manager_tools)

# -------------------------------------------------------------------
# 5️⃣ Conditional function for routing logic
# -------------------------------------------------------------------
def should_continue(state: ManagerState, config: RunnableConfig):
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "continue"

# -------------------------------------------------------------------
# 6️⃣ Define the manager workflow graph
# -------------------------------------------------------------------
manager_workflow = StateGraph(ManagerState)

manager_workflow.add_node("manager_assistant", manager_assistance)
manager_workflow.add_node("manager_tool_node", manager_tool_node)

manager_workflow.add_edge(START, "manager_assistant")
manager_workflow.add_conditional_edges(
    "manager_assistant",
    should_continue,
    {
        "continue": "manager_tool_node",
        "end": END,
    },
)
manager_workflow.add_edge("manager_tool_node", "manager_assistant")

manager_subagent = manager_workflow.compile(
    name="manager_subagent",
    checkpointer=checkpointer,
    store=in_memory_store,
)

# -------------------------------------------------------------------
# 7️⃣ Visualize and test the subagent
# -------------------------------------------------------------------
show_graph(manager_subagent)

if __name__ == "__main__":
    thread_id = uuid.uuid4()
    query = "Show all my assigned tickets and add a note to INC00321."
    config = {"configurable": {"thread_id": thread_id}}

    result = manager_subagent.invoke(
        {"messages": [HumanMessage(content=query)]},
        config=config
    )

    for message in result["messages"]:
        message.pretty_print()
