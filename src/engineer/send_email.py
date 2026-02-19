import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import ssl
from O365 import MSGraphProtocol, FileSystemTokenBackend
#from O365 import Account as O365Account
from O365 import Account
import os
import requests
from textwrap import dedent
import json
from datetime import datetime, timedelta


def send_gmail(sender_email, app_password, recipient_email, subject, body, attachment_path=None):
    # Setup the email
    recipient_email="limon.halder@petabytz.com"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Attach file if provided
    if attachment_path:
        try:
            with open(attachment_path, "rb") as file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())
                encoders.encode_base64(part)
                filename = attachment_path.split("/")[-1].split("\\")[-1]  # Works for Windows & Linux
                part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                msg.attach(part)
        except FileNotFoundError:
            print(f"⚠️ Attachment not found: {attachment_path}")
            
    try:
        # Connect to Gmail's SMTP server
        with smtplib.SMTP_SSL('smtp.gmail.com', 465,context=ssl.create_default_context()) as server:  # Use port 465 (SSL)
            server.login(sender_email, app_password)  # Use the APP PASSWORD here
            server.sendmail(sender_email, recipient_email, msg.as_string())
            print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")



def send_outlook(
    client_id,
    client_secret,
    tenant_id,
    sender_email,
    recipient_email,
    subject,
    body,
    attachment_path=None,
    token_filename='o365_token.txt'
):
    try:
        # 1. Validate inputs
        if not all([client_id, client_secret, tenant_id, sender_email, recipient_email]):
            raise ValueError("Missing required parameters")
        if '@' not in sender_email or '@' not in recipient_email:
            raise ValueError("Invalid email format")

        # 2. Set up authentication
        token_backend = FileSystemTokenBackend(
            token_path=os.path.dirname(os.path.abspath(__file__)),
            token_filename=token_filename
        )

        account = Account(
            (client_id.strip(), client_secret.strip()),
            auth_flow_type='credentials',
            tenant_id=tenant_id.strip(),
            token_backend=token_backend
        )

        # 3. Authenticate
        if not account.is_authenticated:
            print("Authenticating... (check browser or device code)")
            if not account.authenticate(
                scopes=['https://graph.microsoft.com/Mail.Send'],
                redirect_uri='https://login.microsoftonline.com/common/oauth2/nativeclient'
            ):
                raise Exception("Authentication failed")

        # 4. Prepare the body with protected formatting
        body = dedent(body).strip()
        
        # Replace newlines with CRLF and protect empty lines
        formatted_body = []
        for line in body.splitlines():
            if line.strip() == "":  # Empty line
                formatted_body.append(" ")  # Single space preserves empty line
            else:
                formatted_body.append(line)
        
        # Join with CRLF (standard for emails)
        protected_body = "\r\n".join(formatted_body)

        # 5. Create and send message
        mailbox = account.mailbox(sender_email.strip())
        message = mailbox.new_message()
        
        # Set the content as protected body
        message.body = protected_body
        
        # Force plain text interpretation
        message.body_type = 'text'  # Note: 'text' instead of 'plain'
        
        message.to.add([recipient_email.strip()])
        message.subject = subject

        if attachment_path:
            if not os.path.exists(attachment_path):
                raise FileNotFoundError(f"Attachment not found: {attachment_path}")
            message.attachments.add(attachment_path)

        # 6. Verify the message before sending
        print("DEBUG - Final message body:")
        print(repr(message.body))
        
        if message.send():
            print(f"✅ Email sent to {recipient_email}")
            return True
        return False

    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False
    

def send_teams_message(
    client_id: str,
    client_secret: str,
    tenant_id: str,
    recipient_email: str,
    message_content: str
) -> tuple:
    """
    Send Teams message with automatic authentication
    Returns: (success: bool, details: str)
    """
    try:
        # 1. Initialize account with silent auth
        account = Account(
            (client_id, client_secret),
            auth_flow_type='credentials',  # Silent authentication
            tenant_id=tenant_id,
            token_backend=FileSystemTokenBackend(token_filename='.teams_token')
        )

        # 2. Authenticate (fails only if admin consent missing)
        if not account.is_authenticated:
            return False, "Automated auth failed - requires admin consent"

        # 3. Send direct message (queues if recipient offline)
        response = account.connection.post(
            f"https://graph.microsoft.com/v1.0/users/{recipient_email}/chats/sendMessage",
            data=json.dumps({
                "body": {
                    "content": message_content,
                    "contentType": "text"
                }
            }),
            headers={'Content-Type': 'application/json'}
        )

        return response.ok, "Message queued for delivery" if response.ok else f"Error: {response.text}"

    except Exception as e:
        return False, f"Failed: {str(e)}"