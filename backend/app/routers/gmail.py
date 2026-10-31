"""Connect a Gmail account and pull its attachments into the pipeline."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import settings
from ..deps import get_db, get_llm
from ..services import gmail

router = APIRouter(prefix="/gmail", tags=["gmail"])


def _require_config():
    if not (settings.gmail_client_id and settings.gmail_client_secret):
        raise HTTPException(400, "Gmail is not configured (set GCLIENT_ID / GCLIENT_SECRET)")


@router.get("/connect")
def connect():
    _require_config()
    return RedirectResponse(gmail.auth_url())


@router.get("/callback", response_class=HTMLResponse)
def callback(code: str, conn=Depends(get_db)):
    _require_config()
    email = gmail.exchange_code(conn, code)
    return f"<h3>Connected {email}. You can close this tab.</h3>"


@router.post("/sync")
def sync(conn=Depends(get_db), llm=Depends(get_llm)):
    _require_config()
    accounts = conn.execute("SELECT email, refresh_token FROM gmail_accounts").fetchall()
    return {a["email"]: gmail.sync_account(conn, llm, a["email"], a["refresh_token"]) for a in accounts}
