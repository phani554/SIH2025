"""Ingestion workflow. The orchestrator runs the steps in order, calling one layer per step,
and records each one in the trace. Layers never call each other sideways.

    api        auth
    orch       plan_run                     (the bounded plan: max steps, max LLM calls)
    ingestion  upload_validation -> extract_text -> pii_redaction -> injection_scan -> chunking
               -> chunk_department_signals (keyword vote per chunk, no LLM)
    knowledge  sha256_dedupe, save_original, index_chunks, save_results
    llm        embed_chunks, level1_classification, department_decision (Decisions API), level2_extraction
    actions    department_routing (chunks vs Level 1 vs Decisions), review_gate, create_action_items

Manual upload is the only source today.
"""
import json
import re
from dataclasses import dataclass

from ..actions.audit import audit
from ..actions.gate import RULES, review_gate
from ..actions.routing import decide as decide_department
from ..actions.tasks import create_action_items
from ..config import settings
from ..ingestion.chunking import chunk_pages
from ..ingestion.extraction import extract_pages
from ..ingestion.injection import quarantine_injections
from ..ingestion.redaction import redact_pages
from ..ingestion.signals import chunk_signals
from ..ingestion.validation import UploadRejected, safe_file_name, sha256_bytes, validate_upload
from ..knowledge import store
from ..llm.decisions import department_decision
from ..llm.providers import LLMError
from ..llm.structured import MAX_RETRIES, LevelFailed, level1, level2
from .tracing import Tracer

# The plan is fixed and known before we start, so a run is bounded:
# it can never loop or call the LLM more than this.
PLANNED_STEPS = ["auth", "plan_run", "upload_validation", "sha256_dedupe", "save_original", "extract_text",
                 "pii_redaction", "injection_scan", "chunking", "chunk_department_signals", "embed_chunks",
                 "index_chunks", "level1_classification", "department_decision", "level2_extraction",
                 "department_routing", "review_gate", "create_action_items", "save_results"]
LLM_LEVELS = 2
RUN_PLAN = {
    "steps": PLANNED_STEPS,
    "max_retries": MAX_RETRIES,                                   # per LLM level
    "max_llm_calls": LLM_LEVELS * (1 + MAX_RETRIES),              # 2 levels x (1 try + 1 retry) = 4
    "max_steps": len(PLANNED_STEPS) + LLM_LEVELS * MAX_RETRIES,   # 19 + 2 retry steps = 21
    "decision_calls": 1,                                          # Decisions API, no retry
    "embedding_calls": 1,
}


@dataclass
class IngestResult:
    doc_id: int | None
    status: str          # ANALYZED / NEEDS_REVIEW / DUPLICATE
    run_id: int | None = None

    @property
    def duplicate(self) -> bool:
        return self.status == "DUPLICATE"


class RejectedWithTrace(Exception):
    def __init__(self, rejected: UploadRejected, run_id: int):
        super().__init__(str(rejected))
        self.status_code, self.run_id = rejected.status_code, run_id


def process_upload(conn, llm, user, file_name: str, data: bytes,
                   strategy: str | None = None, upload_dir: str | None = None) -> IngestResult:
    """Entry point for one uploaded file. Traces the whole run and saves the trace."""
    tracer = Tracer("ingest", actor=user.name, role=user.role, department=user.department)

    with tracer.step("auth", "api") as s:
        s.input = "X-API-Key header (looked up by its SHA-256 hash)"
        s.output = f"{user.name}: role={user.role}, department={user.department or 'all'}"
        s.detail = {"key_name": user.name, "role": user.role, "department": user.department,
                    "rate_limit": f"{user.calls_this_minute} of {settings.rate_limit_per_minute} calls this minute"}

    with tracer.step("plan_run", "orchestrator") as s:
        tracer.plan = {"plan": RUN_PLAN, "level1": None}
        s.output = (f"{len(PLANNED_STEPS)} steps planned; at most {RUN_PLAN['max_steps']} steps "
                    f"and {RUN_PLAN['max_llm_calls']} LLM calls")
        s.detail = RUN_PLAN

    try:
        with tracer.step("upload_validation", "ingestion") as s:
            s.input = f"{file_name}, {len(data):,} bytes"
            s.detail = validate_upload(file_name, data)
            s.output = f"passed: size, extension {s.detail['extension']}, {s.detail['content']}"
    except UploadRejected as exc:
        tracer.finish("REJECTED", str(exc))
        raise RejectedWithTrace(exc, tracer.save(conn)) from exc

    result = _ingest(conn, llm, tracer, safe_file_name(file_name), data, strategy, upload_dir)
    result.run_id = tracer.save(conn)
    return result


def _ingest(conn, llm, tracer: Tracer, file_name: str, data: bytes, strategy, upload_dir) -> IngestResult:
    reasons: list[str] = []          # why the review gate will hold this document

    with tracer.step("sha256_dedupe", "knowledge") as s:
        digest = sha256_bytes(data)
        existing = store.find_by_sha256(conn, digest)
        s.input = f"sha256 = {digest[:16]}..."
        s.detail = {"sha256": digest, "sql": store.DEDUPE_SQL}
        s.output = f"HIT: same bytes as document #{existing}" if existing else "miss: new document"
    if existing:
        tracer.doc_id = existing
        for name in PLANNED_STEPS[4:]:
            tracer.skip(name, "orchestrator", "duplicate: nothing to do")
        tracer.finish("DUPLICATE", f"Duplicate of document #{existing}; not processed again")
        audit(conn, "DUPLICATE", file_name, existing, actor=tracer.actor)
        return IngestResult(existing, "DUPLICATE")

    with tracer.step("save_original", "knowledge") as s:
        doc_id = store.save_original(conn, digest, file_name, data, f"upload:{tracer.actor}", upload_dir)
        tracer.doc_id = doc_id
        s.output = f"document #{doc_id} created; original kept for traceability"
    audit(conn, "INGEST", f"upload: {file_name}", doc_id, actor=tracer.actor)

    with tracer.step("extract_text", "ingestion") as s:
        pages = extract_pages(file_name, data)
        text = "\n".join(p.text for p in pages)
        words = re.findall(r"[^\W\d_]{2,}", text)
        s.output = f"{len(pages)} page(s), {len(text):,} chars, {len(words)} words"
        s.detail = {"pages": len(pages), "note": "text preview is shown after PII redaction, not here"}
    if len(words) < 5:
        reasons.append("no readable text (empty, scanned or garbage file)")
        for name in PLANNED_STEPS[6:-3]:
            tracer.skip(name, "orchestrator", "no readable text")
        return _finish(conn, tracer, doc_id, None, None, reasons)

    with tracer.step("pii_redaction", "ingestion") as s:
        s.input = f"{len(text):,} chars"
        if settings.redact_pii:
            pages, counts = redact_pages(pages)
            s.output = (", ".join(f"{n} {k}" for k, n in counts.items()) + " masked") if counts else "no PII found"
            s.detail = {"counts": counts, "patterns": "Aadhaar, PAN, Indian mobile, email",
                        "after_redaction_preview": pages[0].text[:600] if pages else ""}
            if counts:
                audit(conn, "REDACT", json.dumps(counts), doc_id)
        else:
            s.status, s.output = "skipped", "REDACT_PII=false"

    with tracer.step("injection_scan", "ingestion") as s:
        pages, quarantined = quarantine_injections(pages)
        s.output = f"{len(quarantined)} line(s) quarantined" if quarantined else "clean"
        s.detail = {"quarantined_lines": quarantined,
                    "effect": "removed before chunking: never indexed, never sent to the LLM"}
        if quarantined:
            reasons.append(f"prompt injection quarantined: \"{quarantined[0]['matched']}\"")
            audit(conn, "INJECTION_FLAG", f"{len(quarantined)} line(s)", doc_id)

    with tracer.step("chunking", "ingestion") as s:
        strategy = strategy or settings.chunk_strategy
        chunks = chunk_pages(pages, settings.chunk_size_words, settings.chunk_overlap_words, strategy)
        s.input = f"strategy={strategy}, size={settings.chunk_size_words} words, overlap={settings.chunk_overlap_words}"
        s.output = f"{len(chunks)} chunk(s)"
        s.detail = {"chunks": [{"no": c.chunk_no, "page": c.page, "words": len(c.text.split()),
                                "preview": c.text[:120]} for c in chunks]}

    with tracer.step("chunk_department_signals", "ingestion") as s:
        signals = chunk_signals(chunks)
        s.input = f"{len(chunks)} chunk(s), keyword lists from departments.py"
        s.output = ", ".join(f"#{x['chunk_no']}→{x['signal'] or '-'}" for x in signals)
        s.detail = {"signals": signals,
                    "note": "a cheap vote per chunk; the document is routed by Level 1, these are evidence"}

    # If the embedding API is down we still keep the text: keyword search keeps working.
    with tracer.step("embed_chunks", "llm") as s:
        s.input = f"{len(chunks)} chunk(s) to {llm.name} embeddings"
        try:
            before = llm.last_embed_tokens
            vectors = llm.embed([c.text for c in chunks])
            s.output = f"{len(vectors)} vector(s) of {len(vectors[0])} dims"
            s.detail = {"model": llm.embed_model,
                        "tokens": {"prompt": llm.last_embed_tokens - before, "completion": 0}}
        except LLMError as exc:
            vectors = [None] * len(chunks)
            s.status, s.output = "failed", f"embedding failed: {str(exc)[:200]}"
            reasons.append("embedding provider unavailable (keyword search only)")

    with tracer.step("index_chunks", "knowledge") as s:
        store.add_chunks(conn, doc_id, chunks, vectors)
        s.output = f"{len(chunks)} chunk(s) stored; FTS5 index updated by trigger" + \
            ("" if vectors[0] is not None else "; no vectors")

    # LEVEL 1: preliminary analysis, from the redacted, quarantined text.
    lvl1 = lvl2 = None
    try:
        lvl1 = level1(llm, tracer, "\n".join(p.text for p in pages))
        tracer.plan["level1"] = lvl1.model_dump()
    except LevelFailed as exc:
        reasons.append(f"Level 1 failed: {str(exc)[:120]}")

    # SECOND OPINION on the department (Decisions API: real probabilities, ~$0.0001).
    decision = None
    if lvl1 and settings.use_decisions_api:
        decision = department_decision(llm, tracer, "\n".join(p.text for p in pages))
    else:
        tracer.skip("department_decision", "llm",
                    "USE_DECISIONS_API=false" if lvl1 else "Level 1 did not produce a valid result")

    # LEVEL 2: entities, from the Level 1 result + the chunks.
    if lvl1:
        try:
            lvl2 = level2(llm, tracer, lvl1, [c.text for c in chunks])
        except LevelFailed as exc:
            reasons.append(f"Level 2 failed: {str(exc)[:120]}")
    else:
        tracer.skip("level2_extraction", "llm", "Level 1 did not produce a valid result")

    routing = None
    if lvl1:
        with tracer.step("department_routing", "actions") as s:
            routing = decide_department(signals, lvl1, decision, settings.department_agreement_threshold)
            s.input = "chunk signals + Level 1 + Decisions API"
            s.output = routing["headline"]
            s.detail = routing
        tracer.plan["routing"] = routing
        if routing["review_reason"]:
            reasons.append(routing["review_reason"])
    else:
        tracer.skip("department_routing", "actions", "no Level 1 result")

    return _finish(conn, tracer, doc_id, lvl1, lvl2, reasons, routing)


def _finish(conn, tracer: Tracer, doc_id: int, lvl1, lvl2, reasons: list[str], routing=None) -> IngestResult:
    with tracer.step("review_gate", "actions") as s:
        status, reasons = review_gate(lvl1, reasons)
        s.output = f"{status}: " + ("; ".join(reasons) if reasons else "all checks passed")
        s.detail = {"rules": RULES, "reasons": reasons, "status": status}

    if lvl2:
        with tracer.step("create_action_items", "actions") as s:
            n = create_action_items(conn, doc_id, lvl2)
            s.output = f"{n} action item(s) created"
    else:
        tracer.skip("create_action_items", "actions", "no Level 2 result")

    with tracer.step("save_results", "knowledge") as s:
        store.save_analysis(conn, doc_id, lvl1, lvl2, status, reasons, routing)
        s.output = f"document #{doc_id} saved as {status}"
    audit(conn, "ANALYZE", json.dumps({"status": status, "reasons": reasons}), doc_id, actor=tracer.actor)

    tracer.plan["used"] = {"steps_run": sum(1 for x in tracer.steps if x.status != "skipped"),
                           "llm_calls": tracer.llm_calls()}
    tracer.finish(status, "; ".join(reasons) if reasons else "classified and extracted")
    return IngestResult(doc_id, status)
