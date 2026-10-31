"""Tracing: record every step of a run so the UI can "show me how".

A run is one upload (kind="ingest") or one question (kind="ask").
A step is one thing the pipeline did, tagged with the LAYER that did it:
    api | orchestrator | ingestion | knowledge | llm | actions

Usage:
    tracer = Tracer("ingest", actor="phani", role="admin")
    with tracer.step("pii_redaction", "ingestion") as s:
        s.input = "1,240 chars"
        text, counts = redact_pii(text)
        s.output = f"{sum(counts.values())} items masked"
        s.detail = {"counts": counts}
    tracer.save(conn)

Steps are kept in memory and written in one go by save(), so a rejected upload
can still be saved after the request's own changes are rolled back.
"""
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

MAX_FIELD_CHARS = 20_000   # keep huge prompts from bloating the database

LAYERS = ("api", "orchestrator", "ingestion", "knowledge", "llm", "actions")


@dataclass
class Step:
    seq: int
    name: str
    layer: str
    status: str = "ok"           # ok | retried | failed | skipped
    started_at: str = ""
    duration_ms: float = 0.0
    input: str = ""              # one-line summary of what went in
    output: str = ""             # one-line summary of what came out
    detail: dict = field(default_factory=dict)   # the drill-down: prompts, scores, SQL...


class Tracer:
    def __init__(self, kind: str, actor: str = "system", role: str | None = None,
                 department: str | None = None):
        self.kind = kind
        self.actor, self.role, self.department = actor, role, department
        self.doc_id: int | None = None
        self.steps: list[Step] = []
        self.plan: dict | None = None        # preliminary analysis + run plan (ingest)
        self.status = "running"
        self.summary = ""
        self.started_at = _now()
        self._t0 = time.perf_counter()
        self.run_id: int | None = None

    @contextmanager
    def step(self, name: str, layer: str):
        assert layer in LAYERS, layer
        s = Step(seq=len(self.steps) + 1, name=name, layer=layer, started_at=_now())
        t0 = time.perf_counter()
        try:
            yield s
        except Exception as exc:
            s.status = "failed"
            s.output = s.output or f"{type(exc).__name__}: {exc}"[:300]
            raise
        finally:
            s.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            self.steps.append(s)

    def skip(self, name: str, layer: str, reason: str) -> None:
        self.steps.append(Step(seq=len(self.steps) + 1, name=name, layer=layer, status="skipped",
                               started_at=_now(), output=reason))

    def llm_calls(self) -> int:
        """Chat-model calls (steps that sent a prompt); embedding calls are not counted."""
        return sum(1 for s in self.steps if "prompt" in s.detail and s.status != "skipped")

    def finish(self, status: str, summary: str = "") -> None:
        self.status, self.summary = status, summary

    def save(self, conn) -> int:
        duration = round((time.perf_counter() - self._t0) * 1000, 2)
        cur = conn.execute(
            """INSERT INTO runs(kind, doc_id, actor, role, department, status, summary,
                                plan_json, started_at, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.kind, self.doc_id, self.actor, self.role, self.department, self.status,
             self.summary, _dump(self.plan) if self.plan else None, self.started_at, duration),
        )
        self.run_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO run_steps(run_id, seq, name, layer, status, started_at, duration_ms,
                                     input_summary, output_summary, detail_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(self.run_id, s.seq, s.name, s.layer, s.status, s.started_at, s.duration_ms,
              s.input[:500], s.output[:500], _dump(s.detail)) for s in self.steps],
        )
        return self.run_id


def load_run(conn, run_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    run = dict(row)
    run["plan"] = json.loads(run.pop("plan_json") or "null")
    run["steps"] = []
    for s in conn.execute("SELECT * FROM run_steps WHERE run_id = ? ORDER BY seq", (run_id,)):
        step = dict(s)
        step["detail"] = json.loads(step.pop("detail_json") or "{}")
        run["steps"].append(step)
    return run


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _dump(obj) -> str:
    """JSON with long strings cut, so one giant prompt can't fill the database."""
    def cut(value):
        if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
            return value[:MAX_FIELD_CHARS] + f"... [{len(value) - MAX_FIELD_CHARS} more chars]"
        if isinstance(value, dict):
            return {k: cut(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cut(v) for v in value]
        return value
    return json.dumps(cut(obj), ensure_ascii=False, default=str)
