# exporter.py
"""CSV exporter for the AI grading pipeline.
Takes a verified grading JSON list, flattens it, computes a total score,
concatenates the per‑criterion feedback, and appends a row to the output CSV.
The function also updates the SQLite submission record to status "exported".
"""
import csv
from pathlib import Path
from typing import List, Dict, Any

from .db import update_status, get_conn
from .config import OUTPUT_CSV_PATH

def _flatten_grading(grading: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert the list of criterion dicts into a single dict.
    Returns a dict with:
        total_score – sum of ``score`` fields
        max_score   – sum of ``max`` fields
        feedback    – concatenated "criterion: score/max – justification (evidence)"
    """
    total = 0
    max_total = 0
    parts = []
    for entry in grading:
        crit = entry["criterion"]
        score = entry["score"]
        max_pts = entry["max"]
        just = entry["justification"]
        ev = entry["evidence"].replace("\n", " ")  # keep one‑line
        total += score
        max_total += max_pts
        parts.append(f"{crit}: {score}/{max_pts} – {just} (evidence: {ev})")
    return {
        "total_score": total,
        "max_score": max_total,
        "feedback": " | ".join(parts),
    }

def export_grade(submission_id: int, student_id: str, grading: List[Dict[str, Any]]) -> None:
    """Append a row to ``OUTPUT_CSV_PATH`` and mark the DB row as exported.
    The CSV columns are: ``student_id,total_score,max_score,feedback``.
    """
    flat = _flatten_grading(grading)
    # Ensure the output directory exists.
    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = OUTPUT_CSV_PATH.is_file()
    with OUTPUT_CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["student_id", "total_score", "max_score", "feedback"])
        writer.writerow([
            student_id,
            flat["total_score"],
            flat["max_score"],
            flat["feedback"],
        ])
    # Update DB status to exported.
    update_status(submission_id, "exported")
    # Optional: delete raw file if RETAIN_RAW is False – caller can handle that.
