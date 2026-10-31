"""Connect a Gmail account and pull its attachments into the pipeline."""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from ..config import settings
from ..deps import get_db, get_llm
from ..security import require_role
from ..services import gmail

router = APIRouter(prefix="/gmail", tags=["gmail"])

# OAuth "state" values we issued: the callback must return one, which blocks CSRF
# (someone tricking an admin's browser into linking the attacker's mailbox).
_pending_states: set[str] = set()


def _require_config():
    if not (settings.gmail_client_id and settings.gmail_client_secret):
        raise HTTPException(400, "Gmail is not configured (set GCLIENT_ID / GCLIENT_SECRET)")


@router.get("/connect")
def connect(user=Depends(require_role("admin"))):
    """Returns the Google consent URL; the frontend opens it in a new tab."""
    _require_config()
    state = secrets.token_urlsafe(16)
    _pending_states.add(state)
    return {"auth_url": gmail.auth_url(state)}


@router.get("/callback", response_class=HTMLResponse)
def callback(code: str, state: str, conn=Depends(get_db)):
    _require_config()
    if state not in _pending_states:
        raise HTTPException(400, "Invalid OAuth state")
    _pending_states.discard(state)
    email = gmail.exchange_code(conn, code)
    return f"<h3>Connected {email}. You can close this tab.</h3>"


@router.post("/sync")
def sync(conn=Depends(get_db), llm=Depends(get_llm), user=Depends(require_role("admin"))):
    _require_config()
    accounts = conn.execute("SELECT email, refresh_token FROM gmail_accounts").fetchall()
    return {a["email"]: gmail.sync_account(conn, llm, a["email"], a["refresh_token"]) for a in accounts}
