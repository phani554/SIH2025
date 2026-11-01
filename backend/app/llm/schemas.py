"""Pydantic models: the contract every LLM reply must meet.

The hackathon version grabbed the first {...} from the model's reply with a regex
and hoped it had the right fields. Now every LLM reply is validated against
Level1Result / Level2Result; if it fails, we retry once and then send the
document to the review queue.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ..departments import DEPARTMENTS

Urgency = Literal["Critical", "High", "Medium", "Low"]
Priority = Literal["High", "Medium", "Low"]
Confidence = Field(ge=0.0, le=1.0)


# ---------- Level 1: preliminary analysis (who is it for, how urgent, what is it) ----------

class DepartmentScore(BaseModel):
    name: str
    confidence: float = Confidence

    @field_validator("name")
    @classmethod
    def known_department(cls, value: str) -> str:
        if value not in DEPARTMENTS:
            raise ValueError(f"department must be one of {DEPARTMENTS}")
        return value


class Level1Result(BaseModel):
    departments: list[DepartmentScore] = Field(min_length=1, max_length=3)   # first = primary
    doc_type: str
    urgency: Urgency
    language: str = "English"
    summary: str = Field(min_length=1, max_length=800)
    reasoning: str
    why_not: str = ""          # the strongest other department and why it lost

    @property
    def primary(self) -> DepartmentScore:
        return self.departments[0]


# ---------- Level 2: KPI / entity extraction ----------

class Entity(BaseModel):
    value: str
    confidence: float = Confidence


class ActionItem(BaseModel):
    action: str
    owner: Optional[str] = None          # role or department, null if not stated
    priority: Priority = "Medium"
    due: Optional[str] = None            # date as written in the document
    confidence: float = Confidence


class Level2Result(BaseModel):
    dates: list[Entity] = Field(default_factory=list)
    amounts: list[Entity] = Field(default_factory=list)
    reference_ids: list[Entity] = Field(default_factory=list)   # invoice no., PO, circular, regulation ids
    vendors: list[Entity] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    deadline: Optional[str] = None
    compliance_required: bool = False
