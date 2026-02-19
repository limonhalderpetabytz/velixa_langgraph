import os
import json
import datetime
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from openai import OpenAI


# Load environment variables
load_dotenv(dotenv_path=".env", override=True)

# SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")
# SNOW_USER = os.getenv("SNOW_USER")
# SNOW_PASS = os.getenv("SNOW_PASS")


SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")
SNOW_USER = os.getenv("SNOW_USER")
SNOW_PASS = os.getenv("SNOW_PASS")
SNOW_API = f"{SNOW_INSTANCE}/api/now/table/incident"

# Initialize ServiceNow client
snow_client = requests.Session()
snow_client.auth = HTTPBasicAuth(SNOW_USER, SNOW_PASS)

# Initialize LLM
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key
llm = ChatOpenAI(model_name="gpt-4", temperature=0)

open_ai_client = OpenAI(api_key=api_key)
model = "gpt-4.1-mini"


# Bot name
bot_name = "ServiceBot"

# Utility function
def remove_think_tags(text):
    return text.replace("<think>", "").replace("</think>", "")

# Placeholder functions (implement as needed)
def save_chat_session(session_id, mail, chat_history):
    pass

def send_email_report(to_email, file_path, subject="Report"):
    pass


def fetch_tickets() -> list:
    """Fetches up to 50 active tickets from ServiceNow, saves locally to tickets.json, and returns the list."""
    params = {
        "sysparm_query": "active=true^stateNOT IN6,7,8^ORDERBYDESCsys_created_on",
        "sysparm_fields": "number,short_description,priority,sys_created_on,caller_id.name,state,description,sla_due",
        "sysparm_display_value": "true",
        "sysparm_limit": 50
    }
    response = snow_client.get(f"{SNOW_INSTANCE}/api/now/table/incident", params=params)
    result = response.json().get('result', [])
    with open("tickets.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    return result


@tool("show_tickets")
def show_tickets(user_input: str, mail: str) -> str:
    """Displays top 5 open tickets sorted by creation date in chatbot-friendly Markdown format."""
    try:
        ticket_data = fetch_tickets()
        number = len(ticket_data)

        prompt = f"""
        You have to show the top five most recent tickets from the {ticket_data}, sorted by sys_created_on (newest first).
        If more than five open tickets exist, show only the five most recent. Otherwise, show all.
        The ServiceNow instance is {SNOW_INSTANCE}.

        Include:
        - Ticket ID, Description, Priority, Age (in hours), SLA Due
        - Assigned Group, Assigned Engineer, Caller
        - Link to the ServiceNow instance

        Format the output as a Markdown table like this:
        | Ticket ID | Description | Priority | Age | SLA Due | Assigned Group | Assigned To | Caller |
        |-----------|-------------|----------|-----|---------|----------------|-------------|--------|
        📊 [View All {number} Tickets in ServiceNow](https://{SNOW_INSTANCE}/nav_to.do?uri=incident_list.do)
        """

        response = open_ai_client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0
        )

        output = remove_think_tags(response.choices[0].message.content)
        bot_message = output

        return bot_message

    except Exception as e:
        return f"⚠️ Error displaying tickets: {e}"



def fetch_individual_ticket(ticket_number: str) -> dict:
    """Fetches details of a specific ServiceNow ticket by ticket number."""
    params = {
        "sysparm_query": f"number={ticket_number}",
        "sysparm_fields": "number,short_description,priority,sys_created_on,caller_id.name,state,description,sla_due",
        "sysparm_display_value": "true"
    }
    response = snow_client.get(f"{SNOW_INSTANCE}/api/now/table/incident", params=params)
    result = response.json().get('result', [])
    return result[0] if result else None


@tool("show_individual_ticket")
def show_individual_ticket(user_input: str, ticket_number: str,mail: str) -> str:
    """Shows a detailed, formatted view of an individual ServiceNow ticket."""
    ticket = fetch_individual_ticket(ticket_number)
    if not ticket:
        return f"⚠️ No ticket found for {ticket_number}."

    prompt = f"""
    Generate a detailed ticket view for {ticket_number}:
    - Client: {ticket['caller_id.name']}
    - Issue: {ticket['description']}
    - Priority: {ticket['priority']}
    - Created: {ticket['sys_created_on']}
    - State: {ticket['state']}

    Include:
    - Bullet-point summary
    - Key info (priority, caller, SLA due, age)
    - Action buttons: [🔄 Change Priority] [📝 Add Comment] [✅ Update State]
    - Direct link: {SNOW_INSTANCE}/nav_to.do?uri=incident.do?sys_id={ticket_number}
    """

    response = open_ai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    output = remove_think_tags(response.choices[0].message.content)
    bot_message = output

    return bot_message


import os
import json
from datetime import datetime
#from langchain.tools import tool

# -------------------------------------------------------
# 1️⃣ Fetch Recent Incidents (compact, limited response)
# -------------------------------------------------------
@tool("fetch_recent_incidents_tool", return_direct=True)
def fetch_recent_incidents_tool(limit: int = 20) -> str:
    """Fetch recent ServiceNow incidents (default 20). Returns JSON string."""
    try:
        params = {
            "sysparm_query": "ORDERBYDESCsys_created_on",
            "sysparm_fields": (
                "number,short_description,priority,"
                "assignment_group.name,state,sys_created_on,caller_id.name"
            ),
            "sysparm_display_value": "true",
            "sysparm_limit": str(limit)
        }
        response = snow_client.get(f"{SNOW_INSTANCE}/api/now/table/incident", params=params)
        response.raise_for_status()
        incidents = response.json().get("result", [])
        return json.dumps(incidents, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error fetching incidents: {e}"})


# -------------------------------------------------------
# 2️⃣ Generate HTML Summary
# -------------------------------------------------------
@tool("generate_incident_report_tool", return_direct=True)
def generate_incident_report_tool(incident_data: str) -> str:
    """Generate compact HTML summary for recent incidents."""
    try:
        incidents = json.loads(incident_data)
        if not isinstance(incidents, list):
            return "<p>⚠️ Invalid incident data format.</p>"

        rows = "".join(
            f"<tr>"
            f"<td>{i.get('number','')}</td>"
            f"<td>{i.get('short_description','')}</td>"
            f"<td>{i.get('priority','')}</td>"
            f"<td>{i.get('assignment_group.name','')}</td>"
            f"<td>{i.get('state','')}</td>"
            f"<td>{i.get('sys_created_on','')}</td>"
            f"<td>{i.get('caller_id.name','')}</td>"
            f"</tr>"
            for i in incidents
        )

        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>ServiceNow Incident Summary</title>
            <style>
                body {{ font-family: Arial, sans-serif; background: #f7f9fc; }}
                h2 {{ color: #003366; }}
                table {{ border-collapse: collapse; width: 100%; background: white; }}
                th, td {{ border: 1px solid #ccc; padding: 6px 8px; }}
                th {{ background: #003366; color: white; }}
                tr:nth-child(even) {{ background: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h2>Recent ServiceNow Incidents</h2>
            <table>
                <tr>
                    <th>Number</th><th>Description</th><th>Priority</th>
                    <th>Group</th><th>State</th><th>Created On</th><th>Caller</th>
                </tr>
                {rows}
            </table>
        </body>
        </html>
        """
    except Exception as e:
        return f"<p>⚠️ Error generating report: {e}</p>"


# -------------------------------------------------------
# 3️⃣ Save HTML Report to Disk
# -------------------------------------------------------
@tool("save_html_report_tool", return_direct=True)
def save_html_report_tool(html_content: str) -> str:
    """Save HTML report to a timestamped file and return the file path."""
    try:
        os.makedirs("reports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join("reports", f"incident_report_{timestamp}.html")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return file_path
    except Exception as e:
        return f"⚠️ Error saving report: {e}"


# -------------------------------------------------------
# 4️⃣ Full Report Generation Pipeline
# -------------------------------------------------------
@tool("report_generation_tool", return_direct=True)
def report_generation_tool(user_input: str, mail: str) -> str:
    """End-to-end pipeline: fetch → generate → save → email (optional)."""
    try:
        # Fetch and process data
        incidents_json = fetch_recent_incidents_tool(limit=20)
        html_report = generate_incident_report_tool(incidents_json)
        file_path = save_html_report_tool(html_report)

        # Optional email dispatch
        if callable(globals().get("send_email_report")):
            send_email_report(mail, file_path, subject="🧾 ServiceNow Incident Summary Report")

        return (
            f"✅ **Report generated successfully!**\n\n"
            f"📄 Saved at: `{file_path}`\n"
            f"📬 Sent to: **{mail}**\n"
        )

    except Exception as e:
        return f"⚠️ Report generation failed: {e}"

manager_tools = [show_tickets, fetch_individual_ticket, show_individual_ticket, fetch_recent_incidents_tool, generate_incident_report_tool, save_html_report_tool, report_generation_tool]
