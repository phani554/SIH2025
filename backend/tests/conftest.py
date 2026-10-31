import os
import sys
import tempfile
from pathlib import Path

# Tests always run offline against a throwaway database.
_tmp = tempfile.mkdtemp()
os.environ["LLM_PROVIDER"] = "offline"
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLES = Path(__file__).resolve().parents[1] / "sample_docs"
