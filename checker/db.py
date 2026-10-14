# db.py
"""SQLite helpers and schema for the local grading pipeline.
Tracks submissions that have been discovered and graded so the process can be
re‑started safely without duplicate work.
"""
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any, List

from .config import BASE_DIR

# Overridable so tests/CI can use an isolated DB instead of data/grading.db.
DB_PATH = Path(os.getenv("GRADING_DB_PATH", str(BASE_DIR / "data" / "grading.db")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    student_id TEXT,
    content_hash TEXT,
    status TEXT NOT NULL CHECK (status IN ('new','parsed','graded','exported')),
    grade_json TEXT,
    processed_at TEXT
);
"""

def get_conn() -> sqlite3.Connection:
    """Return a connection to the SQLite database.
    Caller should close when finished.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create tables if they do not exist. Idempotent.
    Call at the start of the CLI.
    """
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()

def add_submission(file_path: str, student_id: str, content_hash: str) -> int:
    """Insert a new submission record (or ignore if it already exists).
    Returns the row id.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO submissions (file_path, student_id, content_hash, status) VALUES (?,?,?, 'new')",
            (file_path, student_id, content_hash),
        )
        conn.commit()
        return cur.lastrowid

def get_pending() -> List[Dict[str, Any]]:
    """Return submissions with status 'new' (not yet parsed/graded)."""
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM submissions WHERE status = 'new'")
        return [dict(row) for row in cur]

def update_status(submission_id: int, status: str, grade_json: str = None) -> None:
    """Update the processing status and optionally store the grader JSON."""
    with get_conn() as conn:
        if grade_json is not None:
            conn.execute(
                "UPDATE submissions SET status = ?, grade_json = ?, processed_at = datetime('now') WHERE id = ?",
                (status, grade_json, submission_id),
            )
        else:
            conn.execute(
                "UPDATE submissions SET status = ?, processed_at = datetime('now') WHERE id = ?",
                (status, submission_id),
            )
        conn.commit()
