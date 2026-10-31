"""RAG question answering."""
from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..deps import get_db, get_llm
from ..schemas import AskRequest, AskResponse
from ..security import User, allowed_department, current_user
from ..services.llm import LLMError
from ..services.rag import answer_question

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, conn=Depends(get_db), llm=Depends(get_llm),
        user: User = Depends(current_user)):
    department = allowed_department(user, body.department)
    use_hyde = settings.use_hyde if body.use_hyde is None else body.use_hyde
    try:
        return answer_question(conn, llm, body.question, department, body.top_k,
                               use_hyde=use_hyde, mode=body.mode, actor=user.name)
    except LLMError as exc:
        raise HTTPException(502, f"LLM unavailable: {exc}") from exc
