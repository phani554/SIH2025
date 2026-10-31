"""RAG question answering."""
from fastapi import APIRouter, Depends

from ..deps import get_db, get_llm
from ..schemas import AskRequest, AskResponse
from ..services.rag import answer_question

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, conn=Depends(get_db), llm=Depends(get_llm)):
    return answer_question(conn, llm, body.question, body.department, body.top_k)
