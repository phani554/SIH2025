# utils.py
import hashlib, os
from pathlib import Path

def ensure_upload_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def save_bytes_to_file(out_dir: str, filename: str, data: bytes) -> str:
    ensure_upload_dir(out_dir)
    safe_name = filename.replace("/", "_").replace("\\", "_")
    path = os.path.join(out_dir, safe_name)
    with open(path, "wb") as f:
        f.write(data)
    return path
