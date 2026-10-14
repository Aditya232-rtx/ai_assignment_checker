# prechecks.py
"""Safety pre‑checks that run before any LLM grading.
* Empty file detection
* Allowed‑format verification (PDF, DOCX, TXT, source code)
* SHA‑256 content hash for deduplication
* Simple similarity fingerprint (first 8 characters of the hash)
* Optional late‑submission flag (stub – always False for now)
"""
import hashlib
from pathlib import Path
from typing import Tuple, List

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".py", ".java", ".js", ".cpp", ".c", ".go"}

def is_empty(file_path: Path) -> bool:
    """True if the file size is zero bytes."""
    return file_path.stat().st_size == 0

def is_allowed_format(file_path: Path) -> bool:
    """Return True if the extension is in the whitelist."""
    return file_path.suffix.lower() in ALLOWED_EXTENSIONS

def compute_hash(file_path: Path) -> str:
    """Compute a SHA‑256 hex digest of the file’s raw bytes."""
    sha = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()

def similarity_fingerprint(text: str) -> str:
    """Return a short fingerprint for near‑duplicate detection.
    Here we just take the first eight characters of the SHA‑256 of the text.
    In a real system you might use MinHash or embeddings.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]

# Placeholder for a late‑submission check – would compare against a due date.
def is_late(_submission_date: str) -> bool:
    return False

def run_prechecks(file_path: Path) -> Tuple[bool, List[str]]:
    """Run all checks and return ``(passed, messages)``.
    * ``passed`` is ``True`` only if *all* checks succeed.
    * ``messages`` contains human‑readable reasons for any failures.
    """
    msgs: List[str] = []
    if is_empty(file_path):
        msgs.append("File is empty.")
    if not is_allowed_format(file_path):
        msgs.append(f"Unsupported file type: {file_path.suffix}")
    # Late‑submission logic could be added here.
    passed = not msgs
    return passed, msgs
