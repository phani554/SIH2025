import os
import sys
import tempfile
from pathlib import Path

import pytest

# Tests always run offline, with auth ON, against a throwaway database.
_tmp = tempfile.mkdtemp()
os.environ.update({
    "LLM_PROVIDER": "offline",
    "AUTH_ENABLED": "true",
    "REDACT_PII": "true",
    "RATE_LIMIT_PER_MINUTE": "1000",
    "DB_PATH": os.path.join(_tmp, "test.db"),
    "UPLOAD_DIR": os.path.join(_tmp, "uploads"),
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLES = Path(__file__).resolve().parents[1] / "sample_docs"


@pytest.fixture(scope="session")
def keys():
    """One API key per role, created once for the whole test run."""
    from app.db import get_conn, init_db
    from app.security import create_api_key

    init_db()
    with get_conn() as conn:
        return {
            "admin": {"X-API-Key": create_api_key(conn, "admin", "admin")},
            "reviewer": {"X-API-Key": create_api_key(conn, "rev", "reviewer")},
            "finance": {"X-API-Key": create_api_key(conn, "fin", "viewer", "Finance")},
        }
