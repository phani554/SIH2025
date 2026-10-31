"""Two-level document understanding, following the SIH design (README steps 3 and 6).

Level 1  PRELIMINARY ANALYSIS  -> departments (+confidence), doc type, urgency, L1 summary
Level 2  KPI EXTRACTION        -> dates, amounts, reference ids, vendors, action items
                                  (input: the L1 result + the document's chunks)

Each level is ONE LLM call in JSON mode:
  1. send the (PII-redacted) prompt
  2. json.loads + Pydantic validation
  3. if either fails: retry once, telling the model exactly what was wrong
  4. still failing: raise LevelFailed -> the gate sends the document to review

Every attempt is a step in the trace (the orchestrator passes its tracer in):
prompt, raw reply, validation result, tokens.
"""
import json

from pydantic import BaseModel, ValidationError

from ..config import DEPARTMENTS
from .prompts import LEVEL1_PROMPT, LEVEL2_PROMPT
from .providers import LLMError
from .schemas import Level1Result, Level2Result

MAX_RETRIES = 1
MAX_CHARS = 12_000   # bound the prompt; the full text is still indexed for RAG


class LevelFailed(RuntimeError):
    pass


def run_level(llm, tracer, step_name: str, build_prompt, schema: type[BaseModel]):
    """One LLM call + validation, retried once. Each attempt is one traced step."""
    error = ""
    for attempt in range(MAX_RETRIES + 1):
        retry_note = f"Your previous reply was invalid: {error}. Return corrected JSON." if error else ""
        prompt = build_prompt(retry_note)
        with tracer.step(f"{step_name} (attempt {attempt + 1})", "llm") as s:
            s.input = f"{len(prompt):,} chars to {llm.name}"
            s.detail = {"provider": llm.name, "prompt": prompt}
            try:
                reply = llm.generate(prompt, json_mode=True)
            except LLMError as exc:                     # provider down / timeout / 5xx
                s.status, error = "failed", str(exc)[:300]
                s.output = f"provider error: {error}"
                s.detail["error"] = error
                break                                   # retrying a dead provider won't help
            s.detail.update(model=reply.model, raw_response=reply.text,
                            tokens={"prompt": reply.prompt_tokens, "completion": reply.completion_tokens})
            try:
                result = schema.model_validate(json.loads(reply.text))
            except (json.JSONDecodeError, ValidationError) as exc:
                error = _short_error(exc)
                s.status = "retried" if attempt < MAX_RETRIES else "failed"
                s.output = f"validation failed: {error}"
                s.detail["validation"] = {"passed": False, "errors": error}
                continue
            s.output = "valid " + schema.__name__
            s.detail["validation"] = {"passed": True, "schema": schema.__name__}
            s.detail["validated"] = result.model_dump()
            return result
    raise LevelFailed(f"{step_name} failed: {error}")


def level1(llm, tracer, text: str) -> Level1Result:
    return run_level(llm, tracer, "level1_classification",
                     lambda note: LEVEL1_PROMPT.format(departments=json.dumps(DEPARTMENTS),
                                                       retry_note=note, text=text[:MAX_CHARS]),
                     Level1Result)


def level2(llm, tracer, l1: Level1Result, chunks: list[str]) -> Level2Result:
    numbered = "\n".join(f"[{i}] {c}" for i, c in enumerate(chunks, start=1))[:MAX_CHARS]
    return run_level(llm, tracer, "level2_extraction",
                     lambda note: LEVEL2_PROMPT.format(retry_note=note, level1=l1.model_dump_json(),
                                                       chunks=numbered),
                     Level2Result)


def _short_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5])
    return f"not valid JSON ({exc})"
