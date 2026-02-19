# main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import your agents
from user.user_bot import get_agent as get_user_agent
from engineer.engineer_bot import get_agent as get_engineer_agent
from manager.manager_bot import get_agent as get_manager_agent

# --------------------------------------------
# STEP 1: Initialize all agents
# --------------------------------------------
USER_AGENT = get_user_agent()
ENGINEER_AGENT = get_engineer_agent()
MANAGER_AGENT = get_manager_agent()

# --------------------------------------------
# STEP 2: Define routing logic (email -> agent)
# --------------------------------------------
AGENT_MAP = {
    "user@velixa.com": USER_AGENT,
    "engineer@velixa.com": ENGINEER_AGENT,
    "manager@velixa.com": MANAGER_AGENT,
}

# --------------------------------------------
# STEP 3: Setup FastAPI app
# --------------------------------------------
app = FastAPI(
    title="VELIXA Multi-Agent System",
    description="LangGraph-powered orchestrator for User, Engineer, and Manager personas.",
    version="1.0.0"
)

class QueryRequest(BaseModel):
    email: str
    query: str

@app.get("/")
def home():
    return {"status": "running", "message": "VELIXA LangGraph Multi-Agent System active."}

@app.post("/ask")
async def ask_agent(req: QueryRequest):
    """Routes query to the appropriate persona based on email"""
    email = req.email.strip().lower()
    query = req.query.strip()

    agent = AGENT_MAP.get(email)
    if not agent:
        raise HTTPException(status_code=403, detail="Unauthorized email or no persona assigned.")

    try:
        result = agent.invoke({"messages": [query]})
        response = result["messages"][-1].content
        return {"email": email, "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")


