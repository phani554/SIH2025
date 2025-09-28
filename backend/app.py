import base64
# app.py
import os
import time
import base64
import json
from urllib.parse import urlencode
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from dotenv import load_dotenv
import requests

from db import init_db, save_user, get_all_users, get_user_by_id
from google.oauth2.credentials import Credentials

load_dotenv()  # loads .env if present

# config
CLIENT_ID = os.getenv("GCLIENT_ID")
CLIENT_SECRET = os.getenv("GCLIENT_SECRET")
REDIRECT_URI = os.getenv("GREDIRECT_URI", "http://localhost:8000/oauth2/callback")
SCOPE = "https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive.file openid"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")

LABEL_NAME = os.getenv("KMRL_LABEL_NAME", "KMRL_Processed")
DB_PATH = os.getenv("DB_PATH", "db.sqlite")

init_db()

app = FastAPI(title="KMRL Gmail Ingest Backend")

@app.get("/auth/url")
def get_auth_url():
    """
    Returns a Google OAuth consent URL (open this in the browser, sign in, and Google will redirect to /oauth2/callback).
    access_type=offline ensures a refresh_token is issued (use prompt=consent on first run to force refresh token).
    """
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": SCOPE,
        "redirect_uri": REDIRECT_URI,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return JSONResponse({"auth_url": auth_url})

@app.get("/oauth2/callback", response_class=HTMLResponse)
def oauth2_callback(code: str = None, state: str = None):
    """
    Google will redirect here with ?code=<auth_code>.
    We exchange the code for tokens, obtain the user's email (from id_token), and store the tokens in SQLite.
    """
    if not code:
        return HTMLResponse("<h3>No code provided in callback</h3>", status_code=400)

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    r = requests.post(TOKEN_URL, data=data, timeout=15)
    if r.status_code != 200:
        return HTMLResponse(f"<h3>Token exchange failed: {r.status_code}</h3><pre>{r.text}</pre>", status_code=400)
    token = r.json()
    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")
    expires_in = token.get("expires_in", 3600)
    expires_at = int(time.time()) + int(expires_in)
    id_token = token.get("id_token")

    # extract email from id_token payload (quick decode; in prod verify token)
    user_email = None
    try:
        if id_token:
            parts = id_token.split(".")
            if len(parts) >= 2:
                padded = parts[1] + "=" * (-len(parts[1]) % 4)
                payload_bytes = base64.urlsafe_b64decode(padded)
                payload = json.loads(payload_bytes)
                user_email = payload.get("email")
    except Exception:
        user_email = None

    user_id = user_email or f"user-{int(time.time())}"
    save_user(user_id, user_email, refresh_token, access_token, expires_at)
    html = f"""
    <html>
      <body>
        <h3>Authorization successful</h3>
        <p>User: {user_email}</p>
        <p>User ID: {user_id}</p>
        <p>You may close this window. The backend stored tokens successfully.</p>
      </body>
    </html>
    """
    return HTMLResponse(html)

@app.get("/users")
def list_users():
    rows = get_all_users()
    return JSONResponse([{"id": r[0], "email": r[1], "token_expiry": r[4]} for r in rows])

@app.get("/users/{user_id}")
def get_user(user_id: str):
    row = get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="user not found")
    return {"id": row[0], "email": row[1], "token_expiry": row[4]}

@app.get("/")
def index():
    return RedirectResponse("/auth/url")
