"""MetroMind API. Run: uvicorn app.main:app --reload  (from the backend folder)"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .deps import get_llm
from .routers import ask, documents, gmail, review

init_db()

app = FastAPI(title="MetroMind: KMRL Document Intelligence", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(review.router)
app.include_router(gmail.router)


@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": get_llm().name}
