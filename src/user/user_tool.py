
# user_tools.py — LangChain Tool Definitions
from dotenv import load_dotenv
from langchain_core.tools import tool
import requests
from requests.auth import HTTPBasicAuth
import json
import re
import ast  # optional, for safe eval if needed
from langchain_openai import ChatOpenAI # Import the OpenAI chat model
import os
from langchain_core.tools import tool
import requests
from requests.auth import HTTPBasicAuth
import json
from openai import OpenAI
from data_pipeline.ingest import get_answer


from .user_solution_tool import generate_solution, retrieve_solution, get_ticket_answer # OpenAI SDK v1
#from bot import llm  # Import the llm instance from bot.py

# ServiceNow credentials
SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")
SNOW_USER = os.getenv("SNOW_USER")
SNOW_PASS = os.getenv("SNOW_PASS")
SNOW_API = f"{SNOW_INSTANCE}/api/now/table/incident"


# # Example constants (replace with your real credentials and instance)
# INSTANCE = "https://dev185333.service-now.com"
# USER = "admin"
# PASSWORD = "4V!WDd^lUc7y"
# SNOW_API = f"{INSTANCE}/api/now/table/incident"

# Initialize OpenAI client
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import json


# Initialize LLM
load_dotenv(dotenv_path=".env", override=True)
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key


llm = ChatOpenAI(model_name="gpt-4", temperature=0)

# -----------------------------
# -----------------------------
# Helper Functions
# -----------------------------
import requests
from requests.auth import HTTPBasicAuth
import json

def register_user(email, full_name):
    """
    Lookup the user in ServiceNow by email.
    If user does not exist, create them.
    Return the valid sys_id for 'caller_id'.
    """
    lookup_url = f"{SNOW_INSTANCE}/api/now/table/sys_user?sysparm_query=email={email}"
    
    try:
        # Lookup user
        response = requests.get(
            lookup_url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Accept": "application/json"},
            timeout=500
        )
        response.raise_for_status()  # Raises HTTPError if not 2xx
        
        # Parse JSON safely
        try:
            result = response.json().get('result', [])
        except ValueError:
            print(f"Lookup response not valid JSON: {response.text}")
            result = []

        if result:
            # User exists
            return {"sys_id": result[0]['sys_id'], "email": email, "name": full_name}

        # User does not exist → create
        create_payload = {"name": full_name, "email": email, "user_name": email}
        create_resp = requests.post(
            f"{SNOW_INSTANCE}/api/now/table/sys_user",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Content-Type": "application/json"},
            data=json.dumps(create_payload),
            timeout=500
        )
        create_resp.raise_for_status()
        
        try:
            create_result = create_resp.json().get('result', {})
        except ValueError:
            print(f"Create response not valid JSON: {create_resp.text}")
            create_result = {}

        return {
            "sys_id": create_result.get('sys_id'),
            "email": email,
            "name": full_name
        }

    except requests.exceptions.RequestException as e:
        print(f"ServiceNow API request failed: {e}")
        return {"sys_id": None, "email": email, "name": full_name}


def assign_resource(ticket_sys_id: str, role: str) -> str:
    """
    Assign a ticket to the appropriate role/group.

    This is a placeholder function. Replace it with a real ServiceNow API call
    that performs the assignment.

    Parameters:
    - ticket_sys_id (str): The ServiceNow ticket sys_id.
    - role (str): Assignment group/role.

    Returns:
    str: Confirmation message.
    """
    return f"✅ Ticket {ticket_sys_id} created and assigned to role '{role}'."


def infer_priority_and_role(issue_text: str) -> tuple[int, str]:
    """
    Use the LLM to infer ticket priority and assignment role based on the issue description.

    Parameters:
    - issue_text (str): The user’s issue description.

    Returns:
    tuple:
    - priority (int): 1=High, 2=Medium, 3=Low
    - role (str): Assignment group/role in ServiceNow
    """
    prompt = f"""
    You are an IT support assistant.
    Given this user issue, decide:
    1. Priority (1=High, 2=Medium, 3=Low)
    2. Role/assignment group to handle it (e.g., Network, IT Support, Security)

    Issue: {issue_text}

    Respond ONLY in JSON format like:
    {{
        "priority": <1|2|3>,
        "role": "<role_name>"
    }}
    """
    try:
        response = llm([HumanMessage(content=prompt)])
        content = response.content.strip()
        content = content.replace("'", '"')  # Ensure valid JSON
        result = json.loads(content)
        priority = int(result.get("priority", 3))
        role = result.get("role", "IT Support")
        return priority, role
    except Exception as e:
        print(f"⚠️ LLM parse error: {e}")
        return 3, "IT Support"
    

# -----------------------------
# Main Tool
# -----------------------------

@tool
def submit_ticket(issue: str, email: str, full_name: str) -> str:
    """
    Submit a new ServiceNow incident ticket.

    The ticket's priority and assignment group/role are automatically determined 
    by the LLM based on the issue description.

    Parameters:
    - issue (str): User's problem description.
    - email (str): User's email address.
    - full_name (str): User's full name.

    Returns:
    str: Confirmation message including ticket sys_id and assigned group.
    """
    # 1. Get or register user
    user = register_user(email, full_name)
    if not user:
        return f"❌ Failed to register/find user {email}"

    # 2. Use LLM to infer priority & group
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = f"""
    You are a ServiceNow ticket classifier.
    Analyze the issue and decide two things:
    1. The ticket PRIORITY (choose one: Low, Medium, High, Critical)
    2. The ASSIGNMENT GROUP (choose one: Software, Hardware, IT Support, Networking, Machine Learning, or Others)

    Return your answer strictly in JSON format:
    {{
        "priority": "Medium",
        "group": "Software"
    }}

    Issue description:
    {issue}
    """


    try:
        response = llm.invoke(prompt)
        content = response.content.strip()

        # Extract JSON safely
        parsed = json.loads(content)
        priority = parsed.get("priority", "Medium")
        role = parsed.get("group", "Others")
    except Exception as e:
        priority, role = "Medium", "Others"
        print(f"⚠️ LLM classification failed: {e}")

    # 3. Prepare ServiceNow payload
    payload = {
        "short_description": issue.split('.')[0] + '.',
        "description": issue,
        "caller_id": user['sys_id'],
        "u_requested_for": user['sys_id'],
        "impact": priority,
        "urgency": priority,
        "category": "inquiry",
        "assignment_group": role,
        "assigned_to": "",
        "u_email": user['email'],
        "u_full_name": user['name']
    }

    # 4. Submit ticket to ServiceNow
    try:
        response = requests.post(
            SNOW_API,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            data=json.dumps(payload),
            verify=False,
            timeout=500
        )
        response.raise_for_status()
        ticket = response.json().get('result', {})

        # 5. Return confirmation
        return (
            f"✅ Ticket created successfully!\n"
            f"🧠 LLM assigned group: **{role}** | Priority: **{priority}**\n"
            f"🎫 Ticket Number: {ticket.get('number', 'UNKNOWN')}"
        )


    except requests.exceptions.RequestException as e:
        return f"❌ Failed to create ticket: {e}"



# @tool
# def submit_ticket(issue: str, email: str, full_name: str) -> str:
#     """
#     Submit a new ServiceNow incident ticket.

#     The ticket's priority and assignment group/role are automatically determined 
#     by the LLM based on the issue description.

#     Parameters:
#     - issue (str): User's problem description.
#     - email (str): User's email address.
#     - full_name (str): User's full name.

#     Returns:
#     str: Confirmation message including ticket sys_id and assigned role.
#     """
#     # 1. Get or register user
#     user = register_user(email, full_name)
#     if not user:
#         return f"❌ Failed to register/find user {email}"

#     # 2. Determine priority and role via LLM
#     priority, role = infer_priority_and_role(issue)

#     # 3. Prepare ticket payload
#     payload = {
#         "short_description": issue.split('.')[0] + '.',
#         "description": issue,
#         "caller_id": user['sys_id'],       # now points to a valid sys_user
#         "u_requested_for": user['sys_id'],
#         "impact": priority,
#         "urgency": priority,
#         "category": "inquiry",
#         "assignment_group": role,
#         "assigned_to": "",
#         "u_email": user['email'],          # optional field
#         "u_full_name": user['name']        # optional field
#     }


#     # 4. Submit ticket to ServiceNow
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

#         # 5. Return confirmation
#         return assign_resource(ticket.get('sys_id', 'UNKNOWN'), role)

#     except requests.exceptions.RequestException as e:
#         return f"❌ Failed to create ticket: {e}"

# from langchain_core.tools import tool
# from langchain_openai import ChatOpenAI


# @tool
# def submit_ticket(issue: str, email: str, full_name: str):
#     """
#     Submit a new ServiceNow incident ticket.
#     LLM automatically decides priority and role.
#     """
#     # 1. Get or register user
#     user = register_user(email, full_name)
#     if not user:
#         return f"❌ Failed to register/find user {email}"

#     # 2. Let LLM decide priority and role
#     priority, role = infer_priority_and_role(issue)

#     # 3. Prepare payload
#     payload = {
#         "short_description": issue.split('.')[0] + '.',  # First line as short description
#         "description": issue,
#         "caller_id": user['sys_id'],
#         "u_requested_for": user['sys_id'],
#         "impact": priority,
#         "urgency": priority,
#         "category": "inquiry",
#         "assignment_group": role,  # Assign group based on LLM
#         "assigned_to": ""
#     }

#     # 4. Submit ticket
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
#         ticket = response.json()['result']

#         # 5. Assign engineer (optional)
#         return assign_resource(ticket['sys_id'], role)

#     except requests.exceptions.RequestException as e:
#         return f"❌ Failed to create ticket: {e}"


# ------------------------------
# 🔍 Check Ticket Status
# ------------------------------


@tool
def check_status(user_input: str):
    """
    Check the status of a ServiceNow incident ticket.
    Input may include a ticket number like INC0010004.
    """
    match = re.search(r"(INC\d+)", user_input.upper())
    if not match:
        return "⚠️ Please provide a valid ServiceNow incident number (e.g. INC0010004)."

    ticket_id = match.group(1)
    url = f"{SNOW_INSTANCE}/api/now/table/incident?sysparm_query=number={ticket_id}&sysparm_fields=number,state,short_description"
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers=headers,
            verify=False,
            timeout=500
        )
    
        if response.status_code == 200:
            result = response.json()
            if result["result"]:
                ticket = result["result"][0]
                state = ticket.get("state", "Unknown")
                desc = ticket.get("short_description", "No description")
                return f"✅ Ticket **{ticket_id}** is currently in state: **{state}**\n📝 Description: {desc}"
            else:
                return f"⚠️ No ticket found with ID: {ticket_id}"
        else:
            return f"❌ Failed to fetch status. HTTP {response.status_code}: {response.text}"

    except requests.exceptions.RequestException as e:
        return f"❌ Error while checking ticket status: {str(e)}"


# ------------------------------
# 💬 Add Comment to Ticket
# ------------------------------
@tool
def add_comments(user_input: str):
    """
    Add a comment to a ServiceNow ticket.
    Example: 'INC0010006: updated by agent'
    """
    match = re.search(r"(INC\d+)", user_input.upper())
    if not match:
        return "❌ Could not find a valid ticket ID. Use format: INC0010006: your comment"

    ticket_id = match.group(1)
    parts = user_input.split(ticket_id, 1)
    if len(parts) < 2:
        return "❌ No comment text found. Use format: INC0010006: your comment"

    comment = parts[1].strip(": ").strip()
    if not comment:
        return "❌ Comment text is empty. Please provide a comment."

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    query_url = f"{SNOW_INSTANCE}/api/now/table/incident?sysparm_query=number={ticket_id}"

    try:
        response = requests.get(
            query_url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers=headers,
            verify=False,
            timeout=600
        )

        if response.status_code != 200:
            return f"⚠️ Failed to fetch ticket details (HTTP {response.status_code})"

        results = response.json().get("result", [])
        if not results:
            return f"⚠️ No ticket found with ID: {ticket_id}"

        sys_id = results[0]["sys_id"]
        update_url = f"{SNOW_INSTANCE}/api/now/table/incident/{sys_id}"
        update_data = {"work_notes": comment}

        update_response = requests.patch(
            update_url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers=headers,
            data=json.dumps(update_data),
            verify=False,
            timeout=500
        )

        if update_response.status_code in [200, 204]:
            return f"💬 Successfully added comment to '{ticket_id}': '{comment}'"
        else:
            return f"⚠️ Failed to update ticket (HTTP {update_response.status_code})"

    except requests.exceptions.RequestException as e:
        return f"❌ Error while adding comment: {e}"


# ------------------------------
# 💭 Submit Feedback
# ------------------------------
@tool
def submit_feedback(feedback_text: str):
    """Submit user feedback via API."""
    return f"✅ Feedback submitted: '{feedback_text}'"


# ------------------------------
# ❓ Ask Question
# ------------------------------
@tool
def ask_question(question_text: str):
    """Ask a question and get an answer from the knowledge base."""
    answer = f"Answering '{question_text}' from KB..."
    return f"🤔 {answer}"



# ------------------------------
# 🔄 Reopen Ticket
# ------------------------------
@tool
def reopen_ticket(ticket_id: str):
    """Reopen a closed ServiceNow ticket."""
    return f"🔄 Ticket '{ticket_id}' has been reopened"



# -----------------------------
@tool
def show_my_tickets(user_email: str):
    """
    Fetch and return all ServiceNow tickets for a given user email.

    Args:
        user_email (str): The email of the user.

    Returns:
        str: A formatted list of tickets or an error message.
    """
    headers = {"Accept": "application/json"}

    # Step 1: Get user sys_id from email
    user_url = f"{SNOW_INSTANCE}/api/now/table/sys_user"
    user_params = {
        "sysparm_query": f"email={user_email}",
        "sysparm_fields": "sys_id,name,email"
    }

    try:
        user_resp = requests.get(
            user_url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers=headers,
            params=user_params,
            verify=False,
            timeout=600
        )
        user_resp.raise_for_status()
        users = user_resp.json().get("result", [])

        if not users:
            return f"⚠️ No user found with email '{user_email}'. Please check the email."

        user_id = users[0]["sys_id"]

        # Step 2: Fetch tickets for the user
        tickets_url = f"{SNOW_INSTANCE}/api/now/table/incident"
        ticket_fields = ["number", "state", "short_description", "sys_id", "priority", "sys_created_on"]
        ticket_params = {
            "sysparm_query": f"caller_id={user_id}",
            "sysparm_fields": ",".join(ticket_fields),
            "sysparm_limit": 100,
            "sysparm_display_value": "true"
        }

        ticket_resp = requests.get(
            tickets_url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers=headers,
            params=ticket_params,
            verify=False,
            timeout=600
        )
        ticket_resp.raise_for_status()
        tickets = ticket_resp.json().get("result", [])

        if not tickets:
            return f"⚠️ No tickets found for user '{user_email}'."

        # Step 3: Sort tickets by creation date descending
        from dateutil import parser
        tickets.sort(
            key=lambda x: parser.parse(x.get("sys_created_on", "1970-01-01T00:00:00Z")),
            reverse=True
        )

        # Step 4: Format ticket info
        ticket_list = [
            f"🎫 {t['number']} | State: {t.get('state', 'Unknown')} | "
            f"Priority: {t.get('priority', 'N/A')} | Desc: {t.get('short_description', 'No description')}"
            for t in tickets
        ]

        return "\n".join(ticket_list)

    except requests.exceptions.RequestException as e:
        return f"❌ Error fetching tickets for user '{user_email}': {e}"


@tool
def close_ticket(ticket_identifier: str, close_notes: str = "Issue resolved and ticket closed."):
    """
    Close a ServiceNow incident ticket by number or sys_id, with smart error handling.

    Args:
        ticket_identifier (str): Ticket number (e.g., INC0012345) or sys_id of the ticket.
        close_notes (str, optional): Reason or note for closing the ticket.

    Returns:
        str: Success or detailed error message.
    """
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    try:
        # Step 1: Find the ticket by number
        lookup_url = f"{SNOW_INSTANCE}/api/now/table/incident"
        lookup_params = {"sysparm_query": f"number={ticket_identifier}", "sysparm_fields": "sys_id,number,state"}
        lookup_resp = requests.get(
            lookup_url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers=headers,
            params=lookup_params,
            verify=False,
            timeout=600
        )
        lookup_resp.raise_for_status()
        result = lookup_resp.json().get("result", [])

        # If not found by number, assume identifier is sys_id
        if not result:
            sys_id = ticket_identifier
            ticket_number = ticket_identifier
        else:
            sys_id = result[0]["sys_id"]
            ticket_number = result[0]["number"]

        # Step 2: Attempt to close the ticket
        update_url = f"{SNOW_INSTANCE}/api/now/table/incident/{sys_id}"
        payload = {
            "state": "7",  # Typically 7 = Closed in ServiceNow
            "close_notes": close_notes,
            "close_code": "Solved (Permanently)"
        }

        update_resp = requests.patch(
            update_url,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers=headers,
            data=json.dumps(payload),
            verify=False,
            timeout=600
        )

        # Handle common status codes gracefully
        if update_resp.status_code == 403:
            return (
                f"❌ Failed to close ticket '{ticket_number}': You don't have permission to perform this action.\n\n"
                "================================== Ai Message ==================================\n\n"
                f"I'm sorry, but it seems like there was an issue with closing the ticket **{ticket_number}**. "
                "The system returned a *'Forbidden (403)'* error, which usually means:\n"
                "- Your account doesn’t have permission to close tickets, or\n"
                "- The ticket is in a state that doesn’t allow closure.\n\n"
                "Please check your permissions or contact your ServiceNow administrator for help."
            )

        elif update_resp.status_code == 404:
            return (
                f"⚠️ Ticket '{ticket_number}' not found. Please verify the ticket number or sys_id."
            )

        elif not update_resp.ok:
            return (
                f"❌ Failed to close ticket '{ticket_number}'.\n"
                f"ServiceNow returned error code {update_resp.status_code}: {update_resp.text}"
            )

        # Step 3: Success
        return f"✅ Ticket '{ticket_number}' has been successfully closed."

    except requests.exceptions.RequestException as e:
        return f"❌ Network or API error while closing ticket '{ticket_identifier}': {e}"

    except Exception as ex:
        return f"⚠️ Unexpected error while closing ticket '{ticket_identifier}': {ex}"




# @tool
# def show_my_tickets(user_id: str):
#     """
#     Fetch and return all ServiceNow tickets for a given user ID.

#     Args:
#         user_id (str): The sys_id or unique identifier of the user.

#     Returns:
#         list[dict] or str: A list of ticket details, or an error message.
#     """
#     url = f"{INSTANCE}/api/now/table/incident"
#     headers = {"Accept": "application/json"}

#     # Query all tickets where caller_id equals user_id
#     params = {
#         "sysparm_query": f"caller_id={user_id}",
#         "sysparm_fields": "number,state,short_description,sys_id,priority",
#         "sysparm_limit": 100  # Optional, adjust as needed
#     }

#     try:
#         response = requests.get(
#             url,
#             auth=HTTPBasicAuth(USER, PASSWORD),
#             headers=headers,
#             params=params,
#             verify=False,
#             timeout=120
#         )
#         response.raise_for_status()  # Raise exception for HTTP errors

#         tickets = response.json().get("result", [])
#         if not tickets:
#             return f"⚠️ No tickets found for user '{user_id}'."

#         # Format ticket info in a readable way
#         ticket_list = []
#         for t in tickets:
#             ticket_list.append(
#                 f"🎫 {t['number']} | State: {t.get('state', 'Unknown')} | "
#                 f"Priority: {t.get('priority', 'N/A')} | Desc: {t.get('short_description', '')}"
#             )

#         return "\n".join(ticket_list)

#     except requests.exceptions.RequestException as e:
#         return f"❌ Error fetching tickets for user '{user_id}': {e}"



# ------------------------------
# 🧰 Tool Registry
# ------------------------------
# user_tools = {
#     "submit_ticket": submit_ticket,
#     "check_status": check_status,
#     "add_comments": add_comments,
#     "submit_feedback": submit_feedback,
#     "ask_question": ask_question,
#     "reopen_ticket": reopen_ticket,
#     "show_my_tickets": show_my_tickets
# }

@tool
def retrieve_or_generate_solution(query: str, memory: str = "None") -> str:
    """
    First try to retrieve from KB, else generate new solution.
    """
    kb_solution = get_ticket_answer(query)
    if kb_solution:
        print("Retrieved solution from KB.")
        return kb_solution
    else:
        print("No KB solution found, generating new solution.")
        return generate_solution(query, memory)

user_tools = [submit_ticket, check_status, add_comments, submit_feedback, ask_question, reopen_ticket, show_my_tickets, close_ticket, retrieve_or_generate_solution]

