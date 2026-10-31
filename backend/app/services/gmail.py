"""Gmail ingestion (refactor of the hackathon gmail_worker.py).

Same idea as before: OAuth with offline access -> refresh token -> list mails
with attachments -> download -> hand each attachment to ingest_file().
Changes: no hard-coded sender address, id_token is verified, attachments go
through the same pipeline as uploads (dedupe, chunk, embed, analyse).
"""
import base64
from urllib.parse import urlencode

import requests

from ..config import settings
from ..db import audit
from .ingestion import ingest_file

SCOPES = "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/gmail.modify"
SUPPORTED = (".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg")


def auth_url(state: str) -> str:
    params = {
        "state": state,
        "client_id": settings.gmail_client_id,
        "redirect_uri": settings.gmail_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",   # gives us a refresh token
        "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def exchange_code(conn, code: str) -> str:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    resp = requests.post("https://oauth2.googleapis.com/token", timeout=15, data={
        "code": code,
        "client_id": settings.gmail_client_id,
        "client_secret": settings.gmail_client_secret,
        "redirect_uri": settings.gmail_redirect_uri,
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    tokens = resp.json()
    # Verify the id_token signature instead of just base64-decoding it.
    claims = id_token.verify_oauth2_token(tokens["id_token"], google_requests.Request(),
                                          settings.gmail_client_id)
    email = claims["email"]
    conn.execute("INSERT OR REPLACE INTO gmail_accounts(email, refresh_token) VALUES (?, ?)",
                 (email, tokens["refresh_token"]))
    audit(conn, "GMAIL_CONNECT", email)
    return email


def _service(refresh_token: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(None, refresh_token=refresh_token,
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=settings.gmail_client_id,
                        client_secret=settings.gmail_client_secret)
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _attachments(parts: list[dict]):
    """Walk MIME parts recursively and yield (filename, attachment_id)."""
    for part in parts or []:
        name = part.get("filename") or ""
        att_id = part.get("body", {}).get("attachmentId")
        if att_id and name.lower().endswith(SUPPORTED):
            yield name, att_id
        yield from _attachments(part.get("parts"))


def _label_id(service) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == settings.gmail_label:
            return label["id"]
    return service.users().labels().create(userId="me", body={"name": settings.gmail_label}).execute()["id"]


def sync_account(conn, llm, email: str, refresh_token: str, max_messages: int = 25) -> int:
    service = _service(refresh_token)
    label = _label_id(service)
    query = f"{settings.gmail_query} -label:{settings.gmail_label}"
    messages = service.users().messages().list(userId="me", q=query,
                                               maxResults=max_messages).execute().get("messages", [])
    ingested = 0
    for msg in messages:
        if conn.execute("SELECT 1 FROM processed_messages WHERE message_id = ?", (msg["id"],)).fetchone():
            continue
        full = service.users().messages().get(userId="me", id=msg["id"]).execute()
        for name, att_id in _attachments(full["payload"].get("parts")):
            att = service.users().messages().attachments().get(
                userId="me", messageId=msg["id"], id=att_id).execute()
            data = base64.urlsafe_b64decode(att["data"])
            result = ingest_file(conn, llm, name, data, source="gmail")
            ingested += 0 if result.duplicate else 1
        conn.execute("INSERT INTO processed_messages(message_id) VALUES (?)", (msg["id"],))
        service.users().messages().modify(userId="me", id=msg["id"],
                                          body={"addLabelIds": [label]}).execute()
    return ingested
