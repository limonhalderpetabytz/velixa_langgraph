"""
Engineer Tools — For ServiceNow Engineer Actions
------------------------------------------------
These tools allow an engineer subagent to:
- Show assigned tickets
- Retrieve ticket history
- Update ticket state or add notes
- Document solutions
- Review analytics
- AI-based troubleshooting using LLM reasoning
"""


from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import requests
from requests.auth import HTTPBasicAuth
import os
import json
import datetime
import pdfkit  # pip install pdfkit
import os
import datetime
import os
#from weasyprint import HTML  # pip install weasyprint
import os
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from .send_email import send_gmail
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
from dotenv import load_dotenv




# SN_USER = os.getenv("SN_USERNAME")
# SN_PASS = os.getenv("SN_PASSWORD")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# OPENAI_KEY = os.getenv("OPEN_AI_KEY")
# SNOW_API_TABLE = "incident"

# SECRET = os.getenv("CLIENT_SECRET")
# ID = os.getenv("CLIENT_ID")
# TENANT_ID = os.getenv("TENANT_ID")


# ----------------------------- SETUP -----------------------------
load_dotenv(dotenv_path=".env", override=True)

# ServiceNow credentials
SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")
SNOW_USER = os.getenv("SNOW_USER")
SNOW_PASS = os.getenv("SNOW_PASS")
SNOW_API = f"{SNOW_INSTANCE}/api/now/table/incident"
MAIL = os.getenv("MAIL")
GOOG_PASS = os.getenv("GOOG_PASS")

# Initialize LLM for reasoning-based troubleshooting
api_key = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = api_key
llm = ChatOpenAI(model_name="gpt-4", temperature=0)

# ----------------------------- TOOL 1 -----------------------------


@tool("show_assigned_tickets")
def show_assigned_tickets(engineer_email: str) -> str:
    """Retrieve all tickets currently assigned to the engineer."""
    try:
        response = requests.get(
            SNOW_API,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            params={"assigned_to.email": engineer_email},
            headers={"Accept": "application/json"},
           # verify=False
        )
        data = response.json().get("result", [])
        tickets = [t["number"] for t in data]
        return f"Tickets assigned to {engineer_email}: {', '.join(tickets) if tickets else 'No tickets found.'}"
    except Exception as e:
        return f"❌ Failed to retrieve assigned tickets: {e}"

# ----------------------------- TOOL 2 -----------------------------


@tool("get_ticket_details")
def get_ticket_details(ticket_numbers: str, engineer_email: str) -> str:
    """
    Retrieve full details of one or multiple tickets assigned to an engineer.
    
    Args:
        ticket_numbers (str): Comma-separated ticket numbers (e.g., "INC00123,INC00124")
        engineer_email (str): Engineer email to validate assignment
    Returns:
        str: Formatted ticket details
    """
    try:
        ticket_list = [t.strip() for t in ticket_numbers.split(",")]
        results = []
        
        for ticket_number in ticket_list:
            response = requests.get(
                f"{SNOW_API}?number={ticket_number}&assigned_to.email={engineer_email}",
                auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
                headers={"Accept": "application/json"},
                verify=False,
                timeout=120
            )
            data = response.json().get("result", [])
            if not data:
                results.append(f"No ticket {ticket_number} found assigned to {engineer_email}.")
                continue
            ticket = data[0]
            details = (
                f"Ticket Number: {ticket.get('number')}\n"
                f"Short Description: {ticket.get('short_description')}\n"
                f"Description: {ticket.get('description')}\n"
                f"State: {ticket.get('state')}\n"
                f"Priority: {ticket.get('priority')}\n"
                f"Assigned To: {ticket.get('assigned_to', {}).get('display_value', 'Unknown')}\n"
                f"Created On: {ticket.get('sys_created_on')}\n"
                f"Updated On: {ticket.get('sys_updated_on')}\n"
                f"{'-'*40}"
            )
            results.append(details)
        
        return "\n".join(results)
    
    except Exception as e:
        return f"❌ Failed to retrieve ticket details: {e}"



@tool("get_ticket_history")
def get_ticket_history(ticket_number: str) -> str:
    """Retrieve the full ticket history and comments for a specific incident."""
    try:
        response = requests.get(
            f"{SNOW_API}/{ticket_number}",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Accept": "application/json"},
            verify=False
        )
        ticket = response.json().get("result", {})
        history = ticket.get("work_notes", "No history available.")
        return f"History for {ticket_number}: {history}"
    except Exception as e:
        return f"❌ Failed to get history for {ticket_number}: {e}"

# ----------------------------- TOOL 3 -----------------------------
@tool("add_technical_note")
def add_technical_note(ticket_number: str, note: str) -> str:
    """
    Add a technical note (work_notes) to a specific ServiceNow ticket.

    Args:
        ticket_number (str): Ticket number (e.g., INC0010009)
        note (str): Technical note to add

    Returns:
        str: Success/failure message
    """
    try:
        # 1. Get ticket sys_id first
        response = requests.get(
            f"{SNOW_API}?number={ticket_number}",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Accept": "application/json"},
            verify=False
        )
        data = response.json().get("result", [])
        if not data:
            return f"❌ Ticket {ticket_number} not found."
        
        sys_id = data[0]["sys_id"]

        # 2. Update ticket with work_notes
        update_response = requests.patch(
            f"{SNOW_API}/{sys_id}",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={"work_notes": note},
            verify=False
        )
        if update_response.status_code in [200, 201]:
            return f"📝 Note added to {ticket_number}: {note}"
        else:
            return f"❌ Failed to add note, status code: {update_response.status_code}"

    except Exception as e:
        return f"❌ Error adding note: {e}"


# ----------------------------- TOOL 7 -----------------------------
@tool("upload_ticket_resolution")
def upload_ticket_resolution(ticket_number: str, resolution_summary: str, engineer_email: str = None) -> str:
    """
    Upload a resolution or fix summary to a ServiceNow incident.
    This tool is LLM-triggered — when the model calls it, it pushes the resolution 
    to the ServiceNow API and marks the ticket as Resolved.

    Args:
        ticket_number (str): ServiceNow incident number (e.g., INC0010046)
        resolution_summary (str): The AI- or engineer-generated fix or root cause summary
        engineer_email (str, optional): The email of the engineer who resolved the issue

    Returns:
        str: Confirmation message with resolution status
    """
    try:
        # 1️⃣ Get sys_id of the target ticket
        response = requests.get(
            f"{SNOW_API}?number={ticket_number}",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Accept": "application/json"},
            verify=False
        )
        result = response.json().get("result", [])
        if not result:
            return f"❌ Ticket {ticket_number} not found in ServiceNow."

        sys_id = result[0]["sys_id"]

        # 2️⃣ Prepare payload for resolution update
        payload = {
            "state": 6,  # 6 = Resolved
            "close_code": "Solved (Permanently)",
            "close_notes": resolution_summary,
            "work_notes": f"Resolution uploaded by LLM agent: {resolution_summary}"
        }
        if engineer_email:
            payload["resolved_by"] = engineer_email

        # 3️⃣ PATCH request to update the ticket
        update_response = requests.patch(
            f"{SNOW_API}/{sys_id}",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json=payload,
            verify=False
        )

        # 4️⃣ Handle API result
        if update_response.status_code in [200, 201]:
            return (
                f"✅ Successfully uploaded resolution for {ticket_number}.\n"
                f"🧩 Resolution Summary: {resolution_summary}\n"
                f"👨‍💻 Engineer: {engineer_email or 'LLM agent'}"
            )
        else:
            return (
                f"❌ Failed to upload resolution for {ticket_number} "
                f"(HTTP {update_response.status_code}).\n"
                f"Response: {update_response.text}"
            )

    except Exception as e:
        return f"❌ Error uploading resolution: {e}"

# ----------------------------- TOOL 4 (Enhanced) -----------------------------
@tool("update_ticket_state")
def update_ticket_state(
    ticket_number: str,
    state: int,
    close_code: str = None,
    close_notes: str = None
) -> str:
    """
    Update the current state of a ServiceNow ticket (1–8).

    ✅ Automatically checks for required resolution info before closing/resolving tickets.

    Args:
        ticket_number (str): Ticket number (e.g., INC0010047)
        state (int): New state (1–8)
        close_code (str, optional): Closure reason (required for 6, 7, or 8)
        close_notes (str, optional): Closure notes (required for 6, 7, or 8)

    Returns:
        str: Success or failure message
    """
    state_map = {
        1: "New",
        2: "In Progress",
        3: "On Hold",
        6: "Resolved",
        7: "Closed",
        8: "Canceled"
    }

    try:
        # 1️⃣ Validate state
        if state not in state_map:
            return f"❌ Invalid state value: {state}. Must be 1–8."

        # 2️⃣ Require resolution info for closing/resolving/canceling
        if state in [6, 7, 8] and (not close_code or not close_notes):
            return (
                f"⚠️ To move ticket {ticket_number} to '{state_map[state]}', "
                f"you must provide both 'close_code' and 'close_notes'."
            )

        # 3️⃣ Fetch sys_id of the target ticket
        response = requests.get(
            f"{SNOW_API}?number={ticket_number}",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={"Accept": "application/json"},
            verify=False
        )

        data = response.json().get("result", [])
        if not data:
            return f"❌ Ticket {ticket_number} not found in ServiceNow."

        sys_id = data[0]["sys_id"]

        # 4️⃣ Build payload
        payload = {"state": state}
        if close_code:
            payload["close_code"] = close_code
        if close_notes:
            payload["close_notes"] = close_notes

        # 5️⃣ PATCH request to update ticket
        update_response = requests.patch(
            f"{SNOW_API}/{sys_id}",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json=payload,
            verify=False
        )

        # 6️⃣ Handle API result
        if update_response.status_code in [200, 201]:
            msg = f"✅ Ticket {ticket_number} successfully moved to '{state_map[state]}'."
            if close_code and close_notes:
                msg += f"\n🧩 close_code='{close_code}' | close_notes='{close_notes}'"
            return msg
        else:
            return (
                f"❌ Failed to update {ticket_number} (HTTP {update_response.status_code}).\n"
                f"Response: {update_response.text}"
            )

    except Exception as e:
        return f"❌ Error updating {ticket_number}: {e}"

# ----------------------------- TOOL 10 -----------------------------

from fastapi import HTTPException
#from langchain.chat_models import ChatOpenAI
from requests.auth import HTTPBasicAuth
import requests, json, os
#from weasyprint import HTML

@tool("generate_engineer_report_pdf")
def generate_engineer_report_pdf(mail, name):
    """
    Generate a PDF report for an engineer showing all assigned tickets,
    their states, priorities, and summary statistics.
    """

    engineer_mail = mail
    engineer_name = name

    try:
        # ---------- 1) Fetch Tickets from ServiceNow ----------
        params = {
            "sysparm_query": (
                f"active=true^assigned_to.email={engineer_mail}"
                "^stateNOT IN6,7,8^ORDERBYDESCsys_created_on"
            ),
            "sysparm_fields": "number,short_description,priority,sys_created_on,caller_id.name,state,description,assigned_to,assigned_group",
            "sysparm_display_value": "true",
            "sysparm_limit": 50
        }

        response = requests.get(
            f"{SNOW_INSTANCE}/api/now/table/incident",
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            params=params,
            headers={"Accept": "application/json"},
            timeout=(5, 30),
      
        )

        data = response.json().get("result", [])
        ticket_count = len(data)

        # ---------- 2) Prepare Prompt for Analytics ----------
        # prompt = f"""
        # Generate a professional analytics report from this ticket list:
        # {data}

        # Requirements:
        # 1. Extract summary statistics:
        #    - Total tickets
        #    - Pending tickets
        #    - Solved tickets
        #    - Average response time (if possible)
        #    - Priority distribution
        #    - State distribution
        # 2. Include small interactive graphs.
        # 3. Report must be HTML only (no extra text).
        # 4. Use engineer name and group from assigned_to and assigned_group.
        # """
        prompt = f"""
        You are a professional HTML report generator for ServiceNow ticket analytics.

        Generate a clean, modern, and actionable HTML report using ONLY HTML + inline CSS + inline JS.
        Do NOT add any explanation or extra text.

        Input data:
        {data}

        Requirements:
        1. Page title should be "Engineer Ticket Analytics Report".
        2. Include a header with:
        - Engineer name and group (extract from assigned_to and assigned_group)
        - Report date/time
        3. Add a summary section with cards showing:
        - Total tickets
        - Pending tickets
        - Solved tickets
        - Average priority
        - Average response time (if available)
        4. Add a ticket table with columns:
        Ticket Number, Short Description, Caller, Created On, State, Priority
        Show only the latest 20 tickets.
        5. Add a visualization section with two charts:
        - Pie chart for state distribution
        - Bar chart for priority distribution
        6. Use Chart.js via CDN and ensure charts are small, interactive, and responsive.
        7. Styling should be modern dashboard-like (cards, table, clean spacing, light background).
        8. Output ONLY valid HTML code.
        9. Do NOT use markdown or code fences.
        10. Do NOT use the exact HTML from the example, but create a similar layout and style.

        Return ONLY HTML.
        """


        llm = ChatOpenAI(model="gpt-4", temperature=0)

        response = llm.invoke([HumanMessage(content=prompt)])
        html_output = response.content

        # Remove code fences if any were inserted
        html_output = "\n".join(
            [line for line in html_output.splitlines() if not line.strip().startswith("```")]
        )

        print("✅ Analytics generated from LLM.")
        print(html_output)
        # Clean markdown code fences if any
        html_output = "\n".join(
            [line for line in html_output.splitlines() if not line.strip().startswith("```")]
        )

        print("✅ HTML report generated.")
        # ---------- 3) Save HTML Report ----------
        reports_dir = "engineer/engineer_reports"
        os.makedirs(reports_dir, exist_ok=True)

        html_path = os.path.join(reports_dir, "ticket_report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_output)
        
        print(f"✅ HTML report saved at {html_path}.")

        # ---------- 4) Convert HTML to PDF ----------
        # pdf_path = os.path.join(reports_dir, "ticket_report.pdf")
        # HTML(html_path).write_pdf(pdf_path)

        # ---------- 5) Email the PDF ----------
        subject = 'Generated Report by Veli AI'
        body = f"""
        Dear {engineer_name},

        This is an automated email generated by Veli AI.

        Please find attached your analytical report based on your ServiceNow tickets.

        Thank you,
        Veli AI
        """
        send_gmail(MAIL, GOOG_PASS, mail, subject, body, html_path)

        bot_message = "✅ Report generated successfully and sent via email."
        return bot_message

    except Exception as e:
        print(f"❌ Error: {e}")
        return "⚠️ Failed to generate/send the report. Please try again."


# @tool("generate_engineer_report_pdf")
# def generate_engineer_report_pdf(engineer_email: str) -> str:
#     """
#     Generate a PDF report for an engineer showing all assigned tickets,
#     their states, priorities, and summary statistics. Saves the report
#     as a PDF file and returns the file path.

#     Args:
#         engineer_email (str): Email of the engineer

#     Returns:
#         str: File path to view/download the PDF report
#     """
#     try:
#         # 1️⃣ Fetch tickets assigned to the engineer
#         response = requests.get(
#             SNOW_API,
#             auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
#             params={"assigned_to.email": engineer_email, "sysparm_limit": 1000},
#             headers={"Accept": "application/json"},
#             verify=False
#         )
#         data = response.json().get("result", [])
#         if not data:
#             return f"📄 No tickets found assigned to {engineer_email}."

#         # 2️⃣ Create PDF file
#         now = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
#         filename = f"engineer_report_{engineer_email.replace('@','_').replace('.','_')}_{now}.pdf"
#         filepath = os.path.join(".", filename)

#         doc = SimpleDocTemplate(filepath, pagesize=A4)
#         elements = []
#         styles = getSampleStyleSheet()

#         # 3️⃣ Add title and summary
#         elements.append(Paragraph(f"Ticket Report for {engineer_email}", styles['Title']))
#         elements.append(Spacer(1, 12))
#         elements.append(Paragraph(f"Generated on: {now}", styles['Normal']))
#         elements.append(Spacer(1, 12))
#         elements.append(Paragraph(f"Total Tickets: {len(data)}", styles['Normal']))
#         elements.append(Spacer(1, 12))

#         # 4️⃣ Prepare table data
#         table_data = [["Ticket Number", "State", "Priority", "Short Description"]]
#         state_counts = {}
#         priority_counts = {}

#         for ticket in data:
#             number = ticket.get("number")
#             state = ticket.get("state")
#             priority = ticket.get("priority", "N/A")
#             short_desc = ticket.get("short_description", "N/A")

#             state_counts[state] = state_counts.get(state, 0) + 1
#             priority_counts[priority] = priority_counts.get(priority, 0) + 1

#             table_data.append([number, state, priority, short_desc])

#         # 5️⃣ Create table
#         t = Table(table_data, repeatRows=1)
#         t.setStyle(TableStyle([
#             ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
#             ('TEXTCOLOR',(0,0),(-1,0),colors.black),
#             ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
#             ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
#             ('ALIGN',(0,0),(-1,-1),'LEFT'),
#         ]))
#         elements.append(t)
#         elements.append(Spacer(1, 12))

#         # 6️⃣ Add state/priority summary
#         elements.append(Paragraph(f"State Counts: {state_counts}", styles['Normal']))
#         elements.append(Paragraph(f"Priority Counts: {priority_counts}", styles['Normal']))

#         # 7️⃣ Build PDF
#         doc.build(elements)

#         return f"✅ PDF report generated: {filepath}"

#     except Exception as e:
#         return f"❌ Failed to generate PDF report: {e}"

# # ----------------------------- TOOL 4 -----------------------------
# @tool("update_ticket_state")
# def update_ticket_state(ticket_number: str, state: int) -> str:
#     """
#     Update the current state of a ServiceNow ticket using integer values (1-7).
#     Returns a user-friendly message with the status name.

#     Args:
#         ticket_number (str): Ticket number (e.g., INC0010047)
#         state (int): New state as integer (1-7)

#     Returns:
#         str: Success/failure message
#     """
#     # Mapping of integer state to readable names
#     state_map = {
#         1: "New",
#         2: "In Progress",
#         3: "On Hold",
#         6: "Resolved",
#         7: "Closed",
#         8: "Canceled"
#     }

#     try:
#         if state not in state_map:
#             return f"❌ Invalid state value: {state}. Must be an integer from 1 to 8."

#         # 1. Get the ticket sys_id first
#         response = requests.get(
#             f"{SNOW_API}?number={ticket_number}",
#             auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
#             headers={"Accept": "application/json"},
#             verify=False
#         )
#         data = response.json().get("result", [])
#         if not data:
#             return f"❌ Ticket {ticket_number} not found."
        
#         sys_id = data[0]["sys_id"]

#         # 2. Update the ticket state
#         update_response = requests.patch(
#             f"{SNOW_API}/{sys_id}",
#             auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
#             headers={"Content-Type": "application/json", "Accept": "application/json"},
#             json={"state": state},
#             verify=False
#         )

#         if update_response.status_code in [200, 201]:
#             return f"✅ Ticket {ticket_number} status updated to '{state_map[state]}' (state={state})."
#         else:
#             return f"❌ Failed to update ticket {ticket_number}, status code: {update_response.status_code}"

#     except Exception as e:
#         return f"❌ Error updating ticket: {e}"



# # ----------------------------- TOOL 4 -----------------------------
# @tool("update_ticket_state")
# def update_ticket_state(ticket_number: str, state: str) -> str:
#     """
#     Update the current state of a ServiceNow ticket (e.g., In Progress, Resolved, Closed).

#     Args:
#         ticket_number (str): Ticket number (e.g., INC0010047)
#         state (str): New state (e.g., "Resolved")

#     Returns:
#         str: Success/failure message
#     """
#     try:
#         # 1. Get the ticket sys_id first
#         response = requests.get(
#             f"{SNOW_API}?number={ticket_number}",
#             auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
#             headers={"Accept": "application/json"},
#             verify=False
#         )
#         data = response.json().get("result", [])
#         if not data:
#             return f"❌ Ticket {ticket_number} not found."
        
#         sys_id = data[0]["sys_id"]

#         # 2. Update the ticket state
#         update_response = requests.patch(
#             f"{SNOW_API}/{sys_id}",
#             auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
#             headers={"Content-Type": "application/json", "Accept": "application/json"},
#             json={"state": state},
#             verify=False
#         )

#         if update_response.status_code in [200, 201]:
#             return f"✅ Ticket {ticket_number} status updated to '{state}'."
#         else:
#             return f"❌ Failed to update ticket {ticket_number}, status code: {update_response.status_code}"

#     except Exception as e:
#         return f"❌ Error updating ticket: {e}"

# ----------------------------- TOOL 5 -----------------------------
@tool("review_analytics")
def review_analytics(engineer_email: str) -> str:
    """Review performance analytics for a specific engineer."""
    try:
        response = requests.get(
            SNOW_API,
            auth=HTTPBasicAuth(SNOW_USER, SNOW_PASS),
            params={"assigned_to.email": engineer_email, "sysparm_limit": 100},
            headers={"Accept": "application/json"},
            verify=False
        )
        data = response.json().get("result", [])
        resolved = len([t for t in data if t.get("state") in ["Resolved", "Closed"]])
        pending = len([t for t in data if t.get("state") not in ["Resolved", "Closed"]])
        avg_time = "2.1 days"  # Example, you can calculate from actual data
        satisfaction = "96%"   # Placeholder

        return (
            f"📊 Analytics for {engineer_email}:\n"
            f"- Resolved Tickets: {resolved}\n"
            f"- Pending Tickets: {pending}\n"
            f"- Avg Resolution Time: {avg_time}\n"
            f"- Satisfaction: {satisfaction}"
        )
    except Exception as e:
        return f"❌ Failed to load analytics: {e}"

# ----------------------------- TOOL 6 -----------------------------
@tool("ai_troubleshooter")
def ai_troubleshooter(issue_description: str) -> str:
    """Use LLM reasoning to diagnose and suggest fixes for a technical issue."""
    try:
        prompt = f"""
        You are an expert IT support engineer.
        Analyze the following issue and provide:
        1. Root cause (probable reason)
        2. Step-by-step troubleshooting plan
        3. Recommended fix or workaround

        Issue Description:
        {issue_description}
        """
        result = llm.invoke(prompt)
        return f"🤖 AI Troubleshooter Suggestion:\n{result.content.strip()}"
    except Exception as e:
        return f"❌ Failed to analyze issue: {e}"

# ----------------------------- EXPORT TOOLSET -----------------------------
engineer_tools = [
    show_assigned_tickets,
    get_ticket_details,
    get_ticket_history,
    add_technical_note,
    update_ticket_state,
    review_analytics,
    ai_troubleshooter,
    upload_ticket_resolution,
    generate_engineer_report_pdf
]
