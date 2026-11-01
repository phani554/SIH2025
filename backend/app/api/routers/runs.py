"""Read the traces behind "Show me how", and the latest eval report."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ...orchestrator.tracing import load_run
from ..auth import User, current_user, require_role
from ..deps import get_db

router = APIRouter(tags=["runs"])
EVALS_DIR = Path(__file__).resolve().parents[3] / "evals"


@router.get("/runs")
def list_runs(limit: int = 30, conn=Depends(get_db), user: User = Depends(current_user)):
    sql = "SELECT run_id, kind, doc_id, actor, status, summary, started_at, duration_ms FROM runs"
    params: list = []
    if user.role == "viewer":                       # viewers only see their own runs
        sql += " WHERE actor = ?"
        params.append(user.name)
    rows = conn.execute(sql + " ORDER BY run_id DESC LIMIT ?", params + [min(limit, 200)])
    return [dict(r) for r in rows]


@router.get("/runs/{run_id}")
def get_run(run_id: int, conn=Depends(get_db), user: User = Depends(current_user)):
    run = load_run(conn, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if user.role == "viewer" and run["actor"] != user.name:
        raise HTTPException(403, "You can only open your own runs")
    return run


@router.get("/evals/latest")
def latest_eval(user: User = Depends(require_role("admin", "reviewer"))):
    reports = sorted(EVALS_DIR.glob("latest_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise HTTPException(404, "No eval report yet: run python -m scripts.run_evals")
    return json.loads(reports[0].read_text())
