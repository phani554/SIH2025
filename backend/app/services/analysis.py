"""Classify + summarise + extract actions in ONE structured LLM call.

Old version: four chained prompts from the browser (4x latency, 4x cost,
JSON scraped with a regex). New version:
  1. one prompt that asks for JSON matching DocumentAnalysis
  2. validate with Pydantic
  3. on failure, retry once and show the model its validation error
  4. still failing -> raise, and the caller marks the document NEEDS_REVIEW
"""
import json

from pydantic import ValidationError

from ..config import DEPARTMENTS
from ..schemas import DocumentAnalysis
from .llm import LLMError

MAX_CHARS = 30_000   # keep the prompt bounded; long docs are still fully indexed for RAG

PROMPT = """You classify documents for KMRL (Kochi Metro Rail Limited).
Return ONLY a JSON object with exactly these fields:
{{
  "department": one of {departments},
  "secondary_departments": [other relevant departments from the same list],
  "confidence": number 0-1 for the department choice,
  "reasoning": "one or two sentences quoting the document",
  "doc_type": "e.g. Invoice, Safety Circular, Maintenance Report",
  "summary": "3-4 sentence summary",
  "key_points": ["up to 5 short points"],
  "urgency": "Critical" | "High" | "Medium" | "Low",
  "action_items": [{{"action": "...", "owner": role or null, "priority": "High"|"Medium"|"Low", "due": date or null}}],
  "deadline": date string or null,
  "compliance_required": true | false,
  "vendors": ["company names mentioned"],
  "amounts": ["money amounts as written"]
}}
Rules: use only facts in the document. If something is not stated use null or [].
Never invent names, dates or amounts. Translate Malayalam/Hindi terms to English.
{retry_note}
FILE: {file_name}
DOCUMENT:
{text}"""


def analyze_document(llm, file_name: str, text: str) -> DocumentAnalysis:
    retry_note = ""
    last_error = ""
    for _attempt in range(2):
        prompt = PROMPT.format(
            departments=json.dumps(DEPARTMENTS), retry_note=retry_note,
            file_name=file_name, text=text[:MAX_CHARS],
        )
        try:
            raw = llm.generate_json(prompt)
            return DocumentAnalysis.model_validate(raw)
        except (ValidationError, LLMError) as exc:
            last_error = str(exc)[:500]
            retry_note = f"Your previous reply was invalid: {last_error}. Fix it."
    raise LLMError(f"Analysis failed after retry: {last_error}")
