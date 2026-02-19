import os
import asyncio
import httpx
from azure.identity.aio import ClientSecretCredential

# -----------------------------
# CONFIGURATION
# -----------------------------
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GRAPH_SCOPE = "https://graph.microsoft.com/.default"

# -----------------------------
# GET APP TOKEN
# -----------------------------
async def get_app_token():
    credential = ClientSecretCredential(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    token = await credential.get_token(GRAPH_SCOPE)
    return token.token

# -----------------------------
# GET USER BY ID
# -----------------------------
async def get_user_by_id(user_id: str, token: str):
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        user_name = data.get("displayName")
        user_email = data.get("mail") or data.get("userPrincipalName")
        return user_name, user_email

# -----------------------------
# MAIN
# -----------------------------
async def main():
    teams_user_id = "29:1A2B3C4D5E..."  # replace with actual ID
    token = await get_app_token()
    name, email = await get_user_by_id(teams_user_id, token)
    print(f"Name: {name}, Email: {email}")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main())
