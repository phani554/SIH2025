"""API security: who is calling, what they may see, and how often.

admin    everything
reviewer read all departments, approve/correct documents, read the audit log
viewer   read and ask only within their own department
"""
import hashlib
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from ..config import settings
from .deps import get_db

ROLES = ("admin", "reviewer", "viewer")


@dataclass
class User:
    name: str
    role: str
    department: str | None      # None = all departments
    calls_this_minute: int = 0  # shown in the trace next to the rate limit


def hash_key(raw_key: str) -> str:
    # Only the SHA-256 of a key is stored, so a database leak doesn't leak keys.
    # API keys are long and random, so a fast hash is fine; human passwords would need bcrypt.
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(conn, name: str, role: str, department: str | None = None) -> str:
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    raw_key = "mm_" + secrets.token_urlsafe(24)
    conn.execute("INSERT INTO api_keys(key_hash, name, role, department) VALUES (?, ?, ?, ?)",
                 (hash_key(raw_key), name, role, department))
    return raw_key          # shown once, never stored


ANONYMOUS_ADMIN = User("local", "admin", None)   # only when AUTH_ENABLED=false


def current_user(x_api_key: str | None = Header(default=None), conn=Depends(get_db)) -> User:
    if not settings.auth_enabled:
        return ANONYMOUS_ADMIN
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key header")
    row = conn.execute("SELECT name, role, department FROM api_keys WHERE key_hash = ? AND active = 1",
                       (hash_key(x_api_key),)).fetchone()
    if not row:
        raise HTTPException(401, "Invalid API key")
    calls = check_rate_limit(row["name"])
    return User(row["name"], row["role"], row["department"], calls)


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


# Rate limit: sliding 60-second window per key, in memory (resets on restart).
_calls: dict[str, deque] = defaultdict(deque)


def check_rate_limit(who: str) -> int:
    now = time.time()
    calls = _calls[who]
    while calls and now - calls[0] > 60:
        calls.popleft()
    if len(calls) >= settings.rate_limit_per_minute:
        raise HTTPException(429, "Too many requests, slow down")
    calls.append(now)
    return len(calls)
