"""MetroMind API. Run: uvicorn app.main:app --reload  (from the backend folder)"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .departments import DEPARTMENT_DEFINITIONS, ROUTING_RULE
from .db import init_db
from .api.deps import get_llm
from .api.routers import ask, documents, review, runs

init_db()

app = FastAPI(title="MetroMind: KMRL Document Intelligence", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(review.router)
app.include_router(runs.router)


@app.get("/health")
def health():
    llm = get_llm()
    return {"status": "ok", "llm_provider": llm.name, "model": getattr(llm, "model", ""),
            "auth": settings.auth_enabled,
            "chunk_strategy": settings.chunk_strategy, "hyde_default": settings.use_hyde,
            "decisions_api": settings.use_decisions_api and llm.name == "openai"}


@app.get("/departments")
def departments():
    """What each department owns and where its boundary is (public: no document content)."""
    return {"rule": ROUTING_RULE,
            "departments": [{"name": n, "owns": d["owns"], "not": d["not"], "keywords": d["keywords"]}
                            for n, d in DEPARTMENT_DEFINITIONS.items()]}
