"""Pydantic models: the contract for LLM output and for the API.

The hackathon version grabbed the first {...} from the model's reply with a regex
and hoped it had the right fields. Now every LLM reply is validated against
DocumentAnalysis; if it fails, we retry once and then mark the document for review.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .config import DEPARTMENTS

Urgency = Literal["Critical", "High", "Medium", "Low"]
Priority = Literal["High", "Medium", "Low"]


class ActionItem(BaseModel):
    action: str
    owner: Optional[str] = None          # role or department, null if not stated
    priority: Priority = "Medium"
    due: Optional[str] = None            # date as written in the document, null if none


class DocumentAnalysis(BaseModel):
    """One structured LLM call replaces the old chain of four prompts."""
    department: str
    secondary_departments: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    doc_type: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    urgency: Urgency
    action_items: list[ActionItem] = Field(default_factory=list)
    deadline: Optional[str] = None
    compliance_required: bool = False
    vendors: list[str] = Field(default_factory=list)
    amounts: list[str] = Field(default_factory=list)

    @field_validator("department")
    @classmethod
    def known_department(cls, value: str) -> str:
        if value not in DEPARTMENTS:
            raise ValueError(f"department must be one of {DEPARTMENTS}")
        return value

    @field_validator("secondary_departments")
    @classmethod
    def known_secondary(cls, values: list[str]) -> list[str]:
        return [v for v in values if v in DEPARTMENTS]


# ---------- API models ----------

class Citation(BaseModel):
    n: int                 # the [n] used in the answer
    chunk_id: int
    doc_id: int
    file_name: str
    page: Optional[int] = None
    snippet: str
    supported: bool = True # citation check: does the cited chunk back the sentence?


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    department: Optional[str] = None     # filter retrieval to one department
    top_k: int = Field(default=5, ge=1, le=10)
    use_hyde: Optional[bool] = None      # None = USE_HYDE from .env
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool         # False when we answered "Not found in the documents."
    faithfulness: float    # share of answer sentences backed by their cited chunk


class ReviewDecision(BaseModel):
    department: Optional[str] = None     # reviewer can correct the department
    approve: bool = True
