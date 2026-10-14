# local_ingestor.py
"""Scans the OneDrive sync folder for new student submissions.
Each file is identified by its path and a simple student‑id derived from the
filename convention ``{student_id}_...``. Files already present in the SQLite
tracking table with status != 'new' are ignored, making the process
idempotent across restarts.
"""
import re
from pathlib import Path
from typing import Iterator, Tuple

from .config import ONEDRIVE_SYNC_PATH
from .db import add_submission, get_pending

# Allowed extensions – PDF, DOCX, TXT, and common source‑code files.
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".py", ".java", ".js", ".cpp", ".c", ".go"}

def _extract_student_id(filename: str) -> str:
    """Extract the leading token before the first underscore as the student id.
    If the pattern is not present, return ``"unknown"``.
    """
    stem = Path(filename).stem
    match = re.match(r"([^_]+)_", stem)
    return match.group(1) if match else "unknown"

def discover_new_submissions() -> Iterator[Tuple[Path, str]]:
    """Yield ``(file_path, student_id)`` tuples for files that have not been
    processed yet. The function walks the sync directory recursively.
    """
    for file_path in ONEDRIVE_SYNC_PATH.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        # Insert a row (or ignore) – the DB will enforce uniqueness on file_path.
        student_id = _extract_student_id(file_path.name)
        add_submission(str(file_path), student_id, "")  # hash will be filled later
        yield file_path, student_id

def list_pending_files() -> list:
    """Return a list of (id, path, student_id) for submissions still marked as 'new'."""
    rows = get_pending()
    return [(row["id"], row["file_path"], row["student_id"]) for row in rows]
