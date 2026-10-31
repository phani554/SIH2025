"""Request and response models for the HTTP API (validated by FastAPI)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


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
    run_id: Optional[int] = None   # open it in "Show me how"


class ReviewDecision(BaseModel):
    department: Optional[str] = None     # reviewer can correct the department
    approve: bool = True
