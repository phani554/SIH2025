"""Create the demo API keys (and optionally pre-load the sample documents).

    python -m scripts.seed_demo                  # keys only: upload the samples live in the demo
    python -m scripts.seed_demo --load-samples   # also ingest sample_docs/ now
"""
import argparse
from pathlib import Path

from app.db import get_conn, init_db
from app.api.auth import User, create_api_key
from app.llm.providers import get_provider
from app.orchestrator.ingest_flow import RejectedWithTrace, process_upload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-samples", action="store_true")
    args = parser.parse_args()

    init_db()
    llm = get_provider()
    print(f"LLM provider: {llm.name} ({llm.model})")
    with get_conn() as conn:
        if args.load_samples:
            seeder = User("seed-script", "admin", None)
            for path in sorted(Path("sample_docs").iterdir()):
                try:
                    r = process_upload(conn, llm, seeder, path.name, path.read_bytes())
                    print(f"  doc {r.doc_id:>3}  {r.status:<13} run {r.run_id:>3}  {path.name}")
                except RejectedWithTrace as exc:
                    print(f"  rejected       {exc}  ({path.name})")
        print("\nDemo API keys (shown once, paste into the app):")
        print("  admin          ", create_api_key(conn, "demo-admin", "admin"))
        print("  finance viewer ", create_api_key(conn, "finance-desk", "viewer", "Finance"))


if __name__ == "__main__":
    main()
