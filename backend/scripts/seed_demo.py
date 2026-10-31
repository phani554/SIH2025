"""Load the sample KMRL documents and create two demo API keys. Run from backend/:
    python -m scripts.seed_demo
"""
from pathlib import Path

from app.db import get_conn, init_db
from app.security import create_api_key
from app.services.ingestion import ingest_file
from app.services.llm import get_provider


def main():
    init_db()
    llm = get_provider()
    print(f"Using LLM provider: {llm.name}")
    with get_conn() as conn:
        for path in sorted(Path("sample_docs").iterdir()):
            result = ingest_file(conn, llm, path.name, path.read_bytes())
            tag = "duplicate" if result.duplicate else result.status
            print(f"  doc {result.doc_id:>3}  {tag:<13} {path.name}")
        print("\nDemo API keys (shown once, paste into the app):")
        print("  admin          ", create_api_key(conn, "demo-admin", "admin"))
        print("  finance viewer ", create_api_key(conn, "finance-desk", "viewer", "Finance"))


if __name__ == "__main__":
    main()
