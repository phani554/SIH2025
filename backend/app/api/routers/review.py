"""Human-in-the-loop review queue and the audit trail."""
from fastapi import APIRouter, Depends, HTTPException

from ...config import DEPARTMENTS
from ...orchestrator.review_flow import ReviewError, apply_review
from ..auth import User, current_user, require_role
from ..deps import get_db
from ..models import ReviewDecision

router = APIRouter(tags=["review"])


@router.post("/documents/{doc_id}/review")
def review(doc_id: int, decision: ReviewDecision, conn=Depends(get_db),
           user: User = Depends(require_role("admin", "reviewer"))):
    if decision.department and decision.department not in DEPARTMENTS:
        raise HTTPException(400, f"Unknown department {decision.department}")
    try:
        return apply_review(conn, doc_id, decision.department, decision.approve, user.name)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ReviewError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/audit")
def audit_log(limit: int = 50, conn=Depends(get_db), user: User = Depends(require_role("admin", "reviewer"))):
    rows = conn.execute(
        "SELECT audit_id, doc_id, actor, action, detail, at FROM audit_log ORDER BY audit_id DESC LIMIT ?",
        (min(limit, 500),),
    )
    return [dict(r) for r in rows]


@router.get("/stats")
def stats(conn=Depends(get_db), user: User = Depends(current_user)):
    by_status = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM documents GROUP BY status")}
    by_department = {r["name"]: r["n"] for r in conn.execute(
        """SELECT dep.name, COUNT(*) AS n FROM document_departments dd
           JOIN departments dep ON dep.dept_id = dd.dept_id
           WHERE dd.is_primary = 1 GROUP BY dep.name""")}
    return {"by_status": by_status, "by_department": by_department}
