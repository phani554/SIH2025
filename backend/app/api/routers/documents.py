"""Upload, list, inspect and delete documents."""
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ...actions.audit import audit
from ...knowledge.retrieval import docs_in_department
from ...orchestrator.ingest_flow import RejectedWithTrace, process_upload
from ..auth import User, current_user, require_role
from ..deps import get_db, get_llm

router = APIRouter(prefix="/documents", tags=["documents"])


def ensure_can_view(conn, user: User, doc_id: int) -> None:
    """Viewers may only open documents tagged with their department."""
    if user.role == "viewer" and doc_id not in docs_in_department(conn, user.department):
        raise HTTPException(403, "Not your department")


@router.post("")
async def upload(file: UploadFile = File(...), conn=Depends(get_db), llm=Depends(get_llm),
                 user: User = Depends(require_role("admin", "reviewer"))):
    data = await file.read()
    try:
        result = process_upload(conn, llm, user, file.filename or "upload", data)
    except RejectedWithTrace as exc:
        conn.commit()                    # keep the trace of the rejection, then refuse
        raise HTTPException(exc.status_code, {"message": str(exc), "run_id": exc.run_id}) from exc
    return {"doc_id": result.doc_id, "status": result.status, "duplicate": result.duplicate,
            "run_id": result.run_id}


@router.get("")
def list_documents(status: str | None = None, department: str | None = None,
                   conn=Depends(get_db), user: User = Depends(current_user)):
    if user.role == "viewer":
        department = user.department
    rows = [dict(r) for r in conn.execute(
        """SELECT d.doc_id, d.file_name, d.source, d.doc_type, d.urgency, d.confidence,
                  d.status, d.created_at, d.review_reasons, d.routing_json,
                  (SELECT dep.name FROM document_departments dd JOIN departments dep
                     ON dep.dept_id = dd.dept_id
                   WHERE dd.doc_id = d.doc_id AND dd.is_primary = 1) AS department
           FROM documents d ORDER BY d.created_at DESC, d.doc_id DESC""")]
    for r in rows:     # small summaries for the list and the review queue
        r["review_reasons"] = json.loads(r["review_reasons"] or "[]")
        routing = json.loads(r.pop("routing_json") or "null") or {}
        decisions = routing.get("decisions") or {}
        r["routing"] = {"pending_review": bool(routing.get("pending_review")),
                        "candidates": routing.get("candidates", []),
                        "level1_department": routing.get("level1_department"),
                        "top_probabilities": (decisions.get("probabilities") or [])[:3]} if routing else None
    if status:
        rows = [r for r in rows if r["status"] == status]
    if department:
        allowed = docs_in_department(conn, department)
        rows = [r for r in rows if r["doc_id"] in allowed]
    return rows


@router.get("/{doc_id}")
def get_document(doc_id: int, conn=Depends(get_db), user: User = Depends(current_user)):
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    ensure_can_view(conn, user, doc_id)
    doc = dict(row)
    doc.pop("saved_path")                # never expose server paths
    doc["level1"] = json.loads(doc.pop("l1_json") or "null")
    doc["level2"] = json.loads(doc.pop("l2_json") or "null")
    doc["review_reasons"] = json.loads(doc["review_reasons"] or "[]")
    doc["routing"] = json.loads(doc.pop("routing_json") or "null")
    doc["departments"] = [dict(r) for r in conn.execute(
        """SELECT dep.name, dd.is_primary, dd.confidence FROM document_departments dd
           JOIN departments dep ON dep.dept_id = dd.dept_id WHERE dd.doc_id = ?
           ORDER BY dd.is_primary DESC""", (doc_id,))]
    doc["action_items"] = [dict(r) for r in conn.execute(
        "SELECT action, owner, priority, due, confidence FROM action_items WHERE doc_id = ?", (doc_id,))]
    doc["chunks"] = [dict(r) for r in conn.execute(
        "SELECT chunk_no, page, substr(text, 1, 160) AS preview FROM chunks WHERE doc_id = ?"
        " ORDER BY chunk_no", (doc_id,))]
    doc["runs"] = [dict(r) for r in conn.execute(
        "SELECT run_id, status, started_at, duration_ms FROM runs WHERE doc_id = ? AND kind = 'ingest'"
        " ORDER BY run_id DESC", (doc_id,))]
    audit(conn, "VIEW", "", doc_id, actor=user.name)
    return doc


@router.get("/{doc_id}/file")
def download_original(doc_id: int, conn=Depends(get_db), user: User = Depends(require_role("admin", "reviewer"))):
    """Traceability: open the exact original file. The original is NOT masked (it may hold Aadhaar
    numbers or injected text), so only admins and reviewers may download it; viewers see masked chunks."""
    row = conn.execute("SELECT file_name, saved_path FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    ensure_can_view(conn, user, doc_id)
    audit(conn, "DOWNLOAD", "", doc_id, actor=user.name)
    return FileResponse(row["saved_path"], filename=row["file_name"])


@router.delete("/{doc_id}")
def delete_document(doc_id: int, conn=Depends(get_db), user: User = Depends(require_role("admin"))):
    deleted = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Document not found")
    # chunks, departments and action items CASCADE; audit rows keep doc_id = NULL
    audit(conn, "DELETE", f"doc {doc_id}", actor=user.name)
    return {"deleted": doc_id}
