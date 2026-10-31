"""Security helpers, kept in one file so they are easy to find and explain.

1. API keys + roles      who is calling, and what may they see
2. Rate limiting         stop one key from hammering the LLM
3. Upload validation     size limit + check the file's magic bytes, not just its name
4. PII redaction         mask Aadhaar / PAN / phone / email before text leaves the server
5. Prompt-injection scan flag documents that try to give the LLM instructions
"""
import hashlib
import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from .config import settings
from .deps import get_db

# ---------- 1. API keys + roles ----------
# admin    everything
# reviewer read all departments, approve/correct documents
# viewer   read and ask only within their own department

ROLES = ("admin", "reviewer", "viewer")


@dataclass
class User:
    name: str
    role: str
    department: str | None      # None = all departments


def hash_key(raw_key: str) -> str:
    # Store only the SHA-256 of the key, like a password hash: a DB leak doesn't leak keys.
    # (API keys are long and random, so a fast hash is fine; passwords would need bcrypt.)
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(conn, name: str, role: str, department: str | None = None) -> str:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    raw_key = "mm_" + secrets.token_urlsafe(24)
    conn.execute(
        "INSERT INTO api_keys(key_hash, name, role, department) VALUES (?, ?, ?, ?)",
        (hash_key(raw_key), name, role, department),
    )
    return raw_key          # shown once, never stored


ANONYMOUS_ADMIN = User("local", "admin", None)   # used only when AUTH_ENABLED=false


def current_user(x_api_key: str | None = Header(default=None), conn=Depends(get_db)) -> User:
    if not settings.auth_enabled:
        return ANONYMOUS_ADMIN
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key header")
    row = conn.execute("SELECT name, role, department FROM api_keys WHERE key_hash = ? AND active = 1",
                       (hash_key(x_api_key),)).fetchone()
    if not row:
        raise HTTPException(401, "Invalid API key")
    check_rate_limit(row["name"])
    return User(row["name"], row["role"], row["department"])


def require_role(*allowed: str):
    """Usage: user = Depends(require_role("admin", "reviewer"))"""
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(403, f"Role '{user.role}' cannot do this")
        return user
    return checker


def allowed_department(user: User, requested: str | None) -> str | None:
    """Viewers are pinned to their own department, whatever they ask for."""
    if user.role == "viewer":
        if requested and requested != user.department:
            raise HTTPException(403, "You can only search your own department")
        return user.department
    return requested


# ---------- 2. Rate limiting (sliding window, in memory) ----------

_calls: dict[str, deque] = defaultdict(deque)


def check_rate_limit(who: str) -> None:
    now, window = time.time(), 60.0
    calls = _calls[who]
    while calls and now - calls[0] > window:
        calls.popleft()
    if len(calls) >= settings.rate_limit_per_minute:
        raise HTTPException(429, "Too many requests, slow down")
    calls.append(now)


# ---------- 3. Upload validation ----------

MAGIC_BYTES = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
}
TEXT_TYPES = (".txt", ".md", ".csv", ".eml")


def validate_upload(file_name: str, data: bytes) -> None:
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    ext = "." + file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    if ext in MAGIC_BYTES:
        if not any(data.startswith(m) for m in MAGIC_BYTES[ext]):
            raise HTTPException(400, f"File content does not match its {ext} extension")
    elif ext in TEXT_TYPES:
        if b"\x00" in data[:4096]:
            raise HTTPException(400, "Binary content in a text file")
    else:
        raise HTTPException(400, f"Unsupported file type: {ext or 'none'}")


# ---------- 4. PII redaction ----------

PII_PATTERNS = {
    "AADHAAR": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "PHONE": re.compile(r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
}


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace PII with [AADHAAR], [PAN], ... and return how many of each were found."""
    counts = {}
    for label, pattern in PII_PATTERNS.items():
        text, n = pattern.subn(f"[{label}]", text)
        if n:
            counts[label] = n
    return text, counts


# ---------- 5. Prompt-injection scan ----------

INJECTION_PATTERNS = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions"
    r"|disregard (the )?(system|previous) (prompt|instructions)"
    r"|you are now\b"
    r"|reveal (your|the) (system prompt|instructions)"
    r"|act as (an? )?(admin|developer|system)",
    re.IGNORECASE,
)


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION_PATTERNS.search(text))
