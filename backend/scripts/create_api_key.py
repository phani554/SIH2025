"""Create an API key. The key is printed once; only its hash is stored.

    python -m scripts.create_api_key --name phani --role admin
    python -m scripts.create_api_key --name finance-desk --role viewer --department Finance
"""
import argparse

from app.config import DEPARTMENTS
from app.db import get_conn, init_db
from app.api.auth import ROLES, create_api_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--department", choices=DEPARTMENTS)
    args = parser.parse_args()
    if args.role == "viewer" and not args.department:
        parser.error("viewers need --department")

    init_db()
    with get_conn() as conn:
        key = create_api_key(conn, args.name, args.role, args.department)
    print(f"API key for {args.name} ({args.role}): {key}")
    print("Store it now; it cannot be shown again.")


if __name__ == "__main__":
    main()
