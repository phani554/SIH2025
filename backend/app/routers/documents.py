"""Upload, list, inspect and delete documents."""
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..db import audit
from ..deps import get_db, get_llm
from ..services.ingestion import ingest_file
from ..services.llm import LLMError

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@router.post("")
async def upload(file: UploadFile = File(...), conn=Depends(get_db), llm=Depends(get_llm)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 15 MB)")
    try:
        result = ingest_file(conn, llm, file.filename or "upload", data, source="upload")
    except ValueError as exc:            # unsupported type, OCR missing
        raise HTTPException(400, str(exc)) from exc
    except LLMError as exc:              # embedding API down
        raise HTTPException(502, str(exc)) from exc
    return {"doc_id": result.doc_id, "duplicate": result.duplicate, "status": result.status}


@router.get("")
def list_documents(status: str | None = None, department: str | None = None, conn=Depends(get_db)):
    sql = """SELECT d.doc_id, d.file_name, d.source, d.doc_type, d.urgency, d.confidence,
                    d.status, d.created_at,
                    (SELECT dep.name FROM document_departments dd JOIN departments dep
                       ON dep.dept_id = dd.dept_id
                     WHERE dd.doc_id = d.doc_id AND dd.is_primary = 1) AS department
             FROM documents d"""
    rows = [dict(r) for r in conn.execute(sql + " ORDER BY d.created_at DESC, d.doc_id DESC")]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if department:
        rows = [r for r in rows if r["department"] == department]
    return rows


@router.get("/{doc_id}")
def get_document(doc_id: int, conn=Depends(get_db)):
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    doc = dict(row)
    doc["analysis"] = json.loads(doc.pop("analysis_json") or "null")
    doc["departments"] = [dict(r) for r in conn.execute(
        """SELECT dep.name, dd.is_primary, dd.confidence FROM document_departments dd
           JOIN departments dep ON dep.dept_id = dd.dept_id WHERE dd.doc_id = ?
           ORDER BY dd.is_primary DESC""", (doc_id,))]
    doc["action_items"] = [dict(r) for r in conn.execute(
        "SELECT action, owner, priority, due FROM action_items WHERE doc_id = ?", (doc_id,))]
    doc["chunk_count"] = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE doc_id = ?", (doc_id,)).fetchone()[0]
    audit(conn, "VIEW", "", doc_id, actor="user")
    return doc


@router.get("/{doc_id}/file")
def download_original(doc_id: int, conn=Depends(get_db)):
    """Traceability: open the exact original file an answer came from."""
    row = conn.execute("SELECT file_name, saved_path FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    return FileResponse(row["saved_path"], filename=row["file_name"])


@router.delete("/{doc_id}")
def delete_document(doc_id: int, conn=Depends(get_db)):
    deleted = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,)).rowcount
    if not deleted:
        raise HTTPException(404, "Document not found")
    # chunks, departments and action items CASCADE; audit rows keep doc_id = NULL
    audit(conn, "DELETE", f"doc {doc_id}", actor="user")
    return {"deleted": doc_id}
