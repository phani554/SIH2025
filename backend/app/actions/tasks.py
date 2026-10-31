"""Turn Level 2 output into action items that someone can act on."""


def create_action_items(conn, doc_id: int, level2) -> int:
    rows = [(doc_id, a.action, a.owner, a.priority, a.due, a.confidence) for a in level2.action_items]
    conn.executemany(
        "INSERT INTO action_items(doc_id, action, owner, priority, due, confidence) VALUES (?, ?, ?, ?, ?, ?)",
        rows)
    return len(rows)
