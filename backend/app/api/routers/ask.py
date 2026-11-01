"""RAG question answering. The API layer checks who is asking, then hands over to the orchestrator."""
from fastapi import APIRouter, Depends, HTTPException

from ...config import settings
from ...llm.providers import LLMError
from ...orchestrator.ask_flow import answer_question
from ...orchestrator.tracing import Tracer
from ..auth import User, allowed_department, current_user
from ..deps import get_db, get_llm
from ..models import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, conn=Depends(get_db), llm=Depends(get_llm), user: User = Depends(current_user)):
    tracer = Tracer("ask", actor=user.name, role=user.role, department=user.department)
    with tracer.step("auth", "api") as s:
        department = allowed_department(user, body.department)    # 403 if a viewer asks outside
        s.input = f"X-API-Key -> {user.name}, role={user.role}"
        s.output = f"searching department: {department or 'all'}"
        s.detail = {"requested_department": body.department, "effective_department": department,
                    "rule": "viewers are pinned to their own department",
                    "rate_limit": f"{user.calls_this_minute} of {settings.rate_limit_per_minute} calls this minute"}
    use_hyde = settings.use_hyde if body.use_hyde is None else body.use_hyde
    with tracer.step("query_received", "api") as s:
        s.input = body.question
        s.output = "AskRequest schema valid"
        s.detail = {"schema": "question 3-500 chars, top_k 1-10, mode keyword|vector|hybrid",
                    "question": body.question, "mode": body.mode, "hyde": use_hyde, "top_k": body.top_k}
    try:
        return answer_question(conn, llm, body.question, department, body.top_k,
                               use_hyde=use_hyde, mode=body.mode, tracer=tracer)
    except LLMError as exc:
        tracer.finish("FAILED", str(exc)[:200])
        tracer.save(conn)
        conn.commit()
        raise HTTPException(502, f"LLM unavailable: {exc}") from exc
