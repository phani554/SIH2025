"""All settings come from environment variables (.env in development).

Keeping config in one place means no secret ever lives in code,
which was the main security problem in the hackathon version
(the Gemini key sat in front-end JavaScript).
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_embed_model: str = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

    db_path: str = os.getenv("DB_PATH", "metromind.db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    chunk_size_words: int = int(os.getenv("CHUNK_SIZE_WORDS", "200"))
    chunk_overlap_words: int = int(os.getenv("CHUNK_OVERLAP_WORDS", "40"))
    review_threshold: float = float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.6"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    gmail_client_id: str = os.getenv("GCLIENT_ID", "")
    gmail_client_secret: str = os.getenv("GCLIENT_SECRET", "")
    gmail_redirect_uri: str = os.getenv("GREDIRECT_URI", "http://localhost:8000/gmail/callback")
    gmail_query: str = os.getenv("GMAIL_QUERY", "has:attachment is:unread")
    gmail_label: str = os.getenv("GMAIL_LABEL", "KMRL_Processed")

    @property
    def use_gemini(self) -> bool:
        return self.llm_provider == "gemini" and bool(self.gemini_api_key)


settings = Settings()

DEPARTMENTS = [
    "Engineering", "Operations", "Maintenance", "Safety",
    "Finance", "HR", "Legal", "Procurement",
]
