"""Human-in-the-loop review queue and the audit trail."""
from fastapi import APIRouter, Depends, HTTPException

from ...actions.audit import audit
from ...config import DEPARTMENTS
from ...knowledge.store import set_departments
from ..auth import User, current_user, require_role
from ..deps import get_db
from ..models import ReviewDecision

router = APIRouter(tags=["review"])


@router.post("/documents/{doc_id}/review")
def review(doc_id: int, decision: ReviewDecision, conn=Depends(get_db),
           user: User = Depends(require_role("admin", "reviewer"))):
    if not conn.execute("SELECT 1 FROM documents WHERE doc_id = ?", (doc_id,)).fetchone():
        raise HTTPException(404, "Document not found")
    if decision.department:
        if decision.department not in DEPARTMENTS:
            raise HTTPException(400, f"Unknown department {decision.department}")
        set_departments(conn, doc_id, [(decision.department, 1.0)])
    status = "APPROVED" if decision.approve else "NEEDS_REVIEW"
    conn.execute("UPDATE documents SET status = ? WHERE doc_id = ?", (status, doc_id))
    audit(conn, "REVIEW", f"status={status} department={decision.department}", doc_id,
          actor=user.name)
    return {"doc_id": doc_id, "status": status}


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
