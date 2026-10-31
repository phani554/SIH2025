"""FastAPI dependencies: one DB connection per request, one shared LLM provider."""
from functools import lru_cache

from ..db import connect
from ..llm.providers import get_provider


def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@lru_cache
def get_llm():
    return get_provider()
