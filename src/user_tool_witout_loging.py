# # user_tools.py — LangChain Tool Definitions
# from dotenv import load_dotenv
# from langchain_core.tools import tool
# import requests
# from requests.auth import HTTPBasicAuth
# import json
# import re
# from langchain_openai import ChatOpenAI
# import os
# from langchain.schema import HumanMessage

# # -----------------------------
# # ServiceNow Configuration
# # -----------------------------
# INSTANCE = "https://dev185333.service-now.com"
# USER = "admin"
# PASSWORD = "4V!WDd^lUc7y"
# SNOW_API = f"{INSTANCE}/api/now/table/incident"

# # Initialize LLM
# load_dotenv(dotenv_path=".env", override=True)
# api_key = os.getenv("OPENAI_API_KEY")
# os.environ["OPENAI_API_KEY"] = api_key
# llm = ChatOpenAI(model_name="gpt-4", temperature=0)

# # -----------------------------
# # Helper Functions
# # -----------------------------
# def infer_priority_and_role(issue_text: str) -> tuple[int, str]:
#     """
#     Use the LLM to infer ticket priority and assignment role based on the issue description.
#     Returns priority (1=High, 2=Medium, 3=Low) and assignment role.
#     """
#     prompt = f"""
#     You are an IT support assistant.
#     Given this user issue, decide:
#     1. Priority (1=High, 2=Medium, 3=Low)
#     2. Role/assignment group to handle it (e.g., Network, IT Support, Security)

#     Issue: {issue_text}

#     Respond ONLY in JSON format like:
#     {{
#         "priority": <1|2|3>,
#         "role": "<role_name>"
#     }}
#     """
#     try:
#         response = llm([HumanMessage(content=prompt)])
#         content = response.content.strip().replace("'", '"')
#         result = json.loads(content)
#         priority = int(result.get("priority", 3))
#         role = result.get("role", "IT Support")
#         return priority, role
#     except Exception as e:
#         print(f"⚠️ LLM parse error: {e}")
#         return 3, "IT Support"

# def assign_resource(ticket_sys_id: str, role: str) -> str:
#     """Dummy assignment placeholder. Replace with real ServiceNow API logic if needed."""
#     return f"✅ Ticket {ticket_sys_id} created and assigned to role '{role}'."

# # -----------------------------
# # Main Tools
# # -----------------------------
# @tool
# def submit_ticket(issue: str, email: str, full_name: str) -> str:
#     """
#     Submit a new ServiceNow incident ticket for a user without a ServiceNow account.
#     Stores user info in description/custom fields.
#     """
#     priority, role = infer_priority_and_role(issue)

#     payload = {
#         "short_description": issue.split('.')[0] + '.',
#         "description": f"Issue from {full_name} ({email}): {issue}",
#         "impact": priority,
#         "urgency": priority,
#         "category": "inquiry",
#         "assignment_group": role,
#         "assigned_to": "",
#         "u_external_email": email,
#         "u_external_name": full_name
#     }

#     try:
#         response = requests.post(
#             SNOW_API,
#             auth=HTTPBasicAuth(USER, PASSWORD),
#             headers={"Content-Type": "application/json", "Accept": "application/json"},
#             data=json.dumps(payload),
#             verify=False,
#             timeout=120
#         )
#         response.raise_for_status()
#         ticket = response.json().get('result', {})
#         return assign_resource(ticket.get('sys_id', 'UNKNOWN'), role)
#     except requests.exceptions.RequestException as e:
#         return f"❌ Failed to create ticket: {e}"

# @tool
# def check_status(user_input: str):
#     """Check status of a ServiceNow ticket by number."""
#     match = re.search(r"(INC\d+)", user_input.upper())
#     if not match:
#         return "⚠️ Please provide a valid ServiceNow incident number (e.g. INC0010004)."

#     ticket_id = match.group(1)
#     url = f"{INSTANCE}/api/now/table/incident?sysparm_query=number={ticket_id}&sysparm_fields=number,state,short_description"

#     try:
#         response = requests.get(url, auth=HTTPBasicAuth(USER, PASSWORD), headers={"Accept": "application/json"}, verify=False, timeout=120)
#         if response.status_code == 200 and response.json().get("result"):
#             ticket = response.json()["result"][0]
#             return f"✅ Ticket **{ticket_id}** is in state: **{ticket.get('state', 'Unknown')}**\n📝 {ticket.get('short_description', '')}"
#         else:
#             return f"⚠️ No ticket found with ID: {ticket_id}"
#     except requests.exceptions.RequestException as e:
#         return f"❌ Error checking ticket status: {e}"

# @tool
# def add_comments(user_input: str):
#     """Add a comment to a ticket by number."""
#     match = re.search(r"(INC\d+)", user_input.upper())
#     if not match:
#         return "❌ Invalid ticket ID format. Use INCxxxxxxx: comment"

#     ticket_id = match.group(1)
#     comment = user_input.split(ticket_id, 1)[1].strip(": ").strip()
#     if not comment:
#         return "❌ Comment text is empty."

#     # Fetch ticket sys_id
#     try:
#         resp = requests.get(f"{INSTANCE}/api/now/table/incident?sysparm_query=number={ticket_id}", auth=HTTPBasicAuth(USER, PASSWORD), headers={"Accept": "application/json"}, verify=False, timeout=60)
#         result = resp.json().get("result", [])
#         if not result:
#             return f"⚠️ Ticket {ticket_id} not found."
#         sys_id = result[0]["sys_id"]
#         patch_resp = requests.patch(f"{INSTANCE}/api/now/table/incident/{sys_id}", auth=HTTPBasicAuth(USER, PASSWORD), headers={"Content-Type": "application/json"}, data=json.dumps({"work_notes": comment}), verify=False, timeout=120)
#         if patch_resp.ok:
#             return f"💬 Comment added to {ticket_id}: '{comment}'"
#         else:
#             return f"⚠️ Failed to add comment (HTTP {patch_resp.status_code})"
#     except requests.exceptions.RequestException as e:
#         return f"❌ Error adding comment: {e}"

# @tool
# def show_my_tickets(user_email: str):
#     """
#     Fetch tickets submitted by a user using email (without ServiceNow account).
#     Looks for email in 'u_external_email' field.
#     """
#     try:
#         tickets_resp = requests.get(f"{INSTANCE}/api/now/table/incident?sysparm_query=u_external_email={user_email}&sysparm_fields=number,state,short_description,priority,sys_created_on", auth=HTTPBasicAuth(USER, PASSWORD), headers={"Accept": "application/json"}, verify=False, timeout=120)
#         tickets = tickets_resp.json().get("result", [])
#         if not tickets:
#             return f"⚠️ No tickets found for {user_email}."
#         tickets.sort(key=lambda x: x.get("sys_created_on", ""), reverse=True)
#         return "\n".join([f"🎫 {t['number']} | State: {t.get('state','Unknown')} | Priority: {t.get('priority','N/A')} | Desc: {t.get('short_description','')}" for t in tickets])
#     except requests.exceptions.RequestException as e:
#         return f"❌ Error fetching tickets: {e}"

# # -----------------------------
# # Tool Registry
# # -----------------------------
# user_tools = [
#     submit_ticket,
#     check_status,
#     add_comments,
#     show_my_tickets,
# ]
