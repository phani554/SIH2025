"""Audit log: who did what, when. Rows survive document deletion (FK ON DELETE SET NULL)."""


def audit(conn, action: str, detail: str = "", doc_id: int | None = None, actor: str = "system") -> None:
    conn.execute("INSERT INTO audit_log(doc_id, actor, action, detail) VALUES (?, ?, ?, ?)",
                 (doc_id, actor, action, detail))
