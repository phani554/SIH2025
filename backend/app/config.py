"""All settings come from environment variables (.env in development).

Keeping config in one place means no secret ever lives in code,
which was the main security problem in the hackathon version
(an LLM key sat in front-end JavaScript).
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")        # openai | offline
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_embed_model: str = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

    db_path: str = os.getenv("DB_PATH", "metromind.db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    chunk_size_words: int = int(os.getenv("CHUNK_SIZE_WORDS", "200"))
    chunk_overlap_words: int = int(os.getenv("CHUNK_OVERLAP_WORDS", "40"))
    chunk_strategy: str = os.getenv("CHUNK_STRATEGY", "recursive")   # fixed | recursive | sentence
    use_hyde: bool = os.getenv("USE_HYDE", "true").lower() == "true"
    review_threshold: float = float(os.getenv("REVIEW_CONFIDENCE_THRESHOLD", "0.6"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    # Security
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    redact_pii: bool = os.getenv("REDACT_PII", "true").lower() == "true"
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "15"))


    @property
    def use_openai(self) -> bool:
        return self.llm_provider == "openai" and bool(self.openai_api_key)


settings = Settings()

DEPARTMENTS = [
    "Engineering", "Operations", "Maintenance", "Safety",
    "Finance", "HR", "Legal", "Procurement",
]
