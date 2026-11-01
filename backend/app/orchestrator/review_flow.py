"""Human review: the reviewer's decision is the last word on a document.

Three cases, all recorded in the audit log and in the document's routing record:
  - approve, same department   -> APPROVED
  - approve, other department  -> APPROVED, department corrected ("Level 1 said X, reviewer chose Y")
  - reject                     -> REJECTED, no department (nobody can retrieve it)

A document whose department was PENDING (the system was unsure, see actions/routing.py) has no
department and no action items yet. Approving it needs a department; that is the moment
the department gets access and the held action items are created.
"""
import json

from ..actions.audit import audit
from ..actions.tasks import create_action_items
from ..knowledge.store import set_departments
from ..llm.schemas import Level2Result


class ReviewError(ValueError):
    pass


def apply_review(conn, doc_id: int, department: str | None, approve: bool, actor: str) -> dict:
    row = conn.execute("SELECT status, l2_json, routing_json FROM documents WHERE doc_id = ?",
                       (doc_id,)).fetchone()
    if not row:
        raise LookupError("Document not found")
    # A reviewer can decide on anything the machine produced (NEEDS_REVIEW, or overrule ANALYZED),
    # but a human decision is final: APPROVED / REJECTED documents can't be reviewed again.
    if row["status"] not in ("NEEDS_REVIEW", "ANALYZED"):
        raise ReviewError(f"Already decided by a reviewer ({row['status']}); upload a new version to change it")
    routing = json.loads(row["routing_json"] or "null") or {}
    before = conn.execute(
        """SELECT dep.name FROM document_departments dd JOIN departments dep ON dep.dept_id = dd.dept_id
           WHERE dd.doc_id = ? AND dd.is_primary = 1""", (doc_id,)).fetchone()
    before = before["name"] if before else None

    if not approve:
        set_departments(conn, doc_id, [])
        conn.execute("DELETE FROM action_items WHERE doc_id = ?", (doc_id,))
        routing.update(reviewed_by=actor, review_outcome="rejected")
        conn.execute("UPDATE documents SET status = 'REJECTED', routing_json = ? WHERE doc_id = ?",
                     (json.dumps(routing), doc_id))
        audit(conn, "REVIEW", f"status=REJECTED department {before or 'pending'} -> none", doc_id, actor=actor)
        return {"doc_id": doc_id, "status": "REJECTED", "department": None}

    department = department or before
    if not department:
        raise ReviewError("This document has no department yet: pick one before approving")

    if department != before:
        set_departments(conn, doc_id, [(department, 1.0)])
    created = 0
    has_items = conn.execute("SELECT 1 FROM action_items WHERE doc_id = ?", (doc_id,)).fetchone()
    if row["l2_json"] and not has_items:      # items were held while the department was pending
        created = create_action_items(conn, doc_id, Level2Result.model_validate_json(row["l2_json"]))

    machine = routing.get("level1_department")
    routing.update(reviewed_by=actor, review_outcome="approved", reviewer_department=department,
                   final_department=department, pending_review=False,
                   reviewer_note=(f"Reviewer chose {department}" +
                                  (f" (Level 1 had said {machine})" if machine and machine != department
                                   else " (agrees with Level 1)" if machine else "")))
    conn.execute("UPDATE documents SET status = 'APPROVED', routing_json = ? WHERE doc_id = ?",
                 (json.dumps(routing), doc_id))
    audit(conn, "REVIEW", f"status=APPROVED department {before or 'pending'} -> {department}; "
                          f"{created} held action item(s) created", doc_id, actor=actor)
    return {"doc_id": doc_id, "status": "APPROVED", "department": department, "action_items_created": created}
