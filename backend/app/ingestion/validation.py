"""Upload validation and fingerprinting: the first gate a file passes."""
import hashlib
import os

from ..config import settings

MAGIC_BYTES = {                  # what the first bytes of a real file of this type look like
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
}
TEXT_TYPES = (".txt", ".md", ".csv")


class UploadRejected(ValueError):
    """The API turns this into a 4xx response (the run is still traced)."""
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def validate_upload(file_name: str, data: bytes) -> dict:
    """Size limit, extension allowlist, magic bytes. Returns what was checked, or raises."""
    size_mb = len(data) / (1024 * 1024)
    ext = "." + file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    checks = {"size_mb": round(size_mb, 3), "max_mb": settings.max_upload_mb, "extension": ext or "none"}
    if size_mb > settings.max_upload_mb:
        raise UploadRejected(413, f"File too large ({size_mb:.1f} MB, max {settings.max_upload_mb} MB)")
    if not data:
        raise UploadRejected(400, "Empty file")
    if ext in MAGIC_BYTES:
        if not any(data.startswith(m) for m in MAGIC_BYTES[ext]):
            raise UploadRejected(400, f"File content does not match its {ext} extension")
        checks["content"] = "magic bytes match"
    elif ext in TEXT_TYPES:
        if b"\x00" in data[:4096]:
            raise UploadRejected(400, "Binary content in a text file")
        checks["content"] = "text, no binary bytes"
    else:
        raise UploadRejected(400, f"Unsupported file type: {ext or 'none'}")
    return checks


def sha256_bytes(data: bytes) -> str:
    """Fingerprint of the exact bytes: the same file uploaded twice has the same hash."""
    return hashlib.sha256(data).hexdigest()


def safe_file_name(name: str) -> str:
    return os.path.basename(name).replace("..", "_") or "file"
