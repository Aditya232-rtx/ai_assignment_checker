# cli.py
"""Command‑line interface for the local AI Assignment Checker.
Commands:
  * ``watch`` – continuously poll the OneDrive sync folder for new files.
  * ``grade-all`` – batch‐process every file marked as ``new`` in SQLite.
  * ``eval`` – compare the generated CSV against a gold‑standard CSV (optional).
All commands accept ``--rubric <path>`` to load the grading rubric.
"""
import argparse
import json
import time
import sys
import os
from pathlib import Path

# Absolute imports – this script is executed directly, so we need the full package path.
from checker.config import ONEDRIVE_SYNC_PATH, DRY_RUN, RETAIN_RAW, OUTPUT_CSV_PATH
from checker.local_ingestor import discover_new_submissions, list_pending_files
from checker.parser import parse_file
from checker.prechecks import run_prechecks, compute_hash, similarity_fingerprint
from checker.rubric import load_rubric
from checker.agents.grader import grade_submission
from checker.agents.verifier import verify_grading
from checker.exporter import export_grade
from checker.db import get_pending, update_status, get_conn


def _process_one(file_path: Path, student_id: str, rubric: dict) -> None:
    """Full pipeline for a single submission.
    1️⃣ Parse → 2️⃣ Pre‑checks → 3️⃣ Grade → 4️⃣ Verify → 5️⃣ Export.
    """
    # 1️⃣ Parse file
    text, _ = parse_file(file_path)

    # 2️⃣ Pre‑checks (includes empty‑file, format, etc.)
    passed, msgs = run_prechecks(file_path)
    if not passed:
        print(f"[SKIP] {file_path.name}: {'; '.join(msgs)}")
        # mark the real row as handled (was hardcoded id=0 — never matched)
        with get_conn() as conn:
            cur = conn.execute("SELECT id FROM submissions WHERE file_path = ?", (str(file_path),))
            row = cur.fetchone()
        if row:
            update_status(row["id"], "graded")
        return

    # 3️⃣ Grade with LLM
    grading = grade_submission(rubric, text)

    # 4️⃣ Verify the grading
    verification = verify_grading(rubric, text, grading)
    conf = verification.get("confidence", 0)
    if conf < 0.7:
        print(f"[FLAG] Low confidence ({conf:.2f}) for {file_path.name}")
        # Mark as graded (NOT left as 'new') so it isn't re-graded forever;
        # the human-review queue is anything with FLAG in the run log.
        with get_conn() as conn:
            cur = conn.execute("SELECT id FROM submissions WHERE file_path = ?", (str(file_path),))
            row = cur.fetchone()
        if row:
            update_status(row["id"], "graded", grade_json=json.dumps(grading))
    else:
        # 5️⃣ Export to CSV
        # Find the DB row id for this file (simple lookup by path)
        with get_conn() as conn:
            cur = conn.execute("SELECT id FROM submissions WHERE file_path = ?", (str(file_path),))
            row = cur.fetchone()
            sub_id = row["id"] if row else None
        if sub_id is None:
            # This should not happen – insert a placeholder record.
            sub_id = 0
        export_grade(sub_id, student_id, grading)
        print(f"[DONE] Exported grade for {student_id} ({file_path.name})")

    # Optional raw‑file cleanup
    if not RETAIN_RAW:
        try:
            file_path.unlink()
        except Exception:
            pass

def _process_pending(rubric_path: Path) -> None:
    """Process all pending submissions in the SQLite table.
    Discovers new files in the sync folder first — previously ``grade-all``
    only looked at the DB, so fresh folder files were never picked up.
    """
    rubric = load_rubric(rubric_path)
    list(discover_new_submissions())
    pending = get_pending()
    if not pending:
        print("[INFO] No new submissions to process.")
        return
    for row in pending:
        file_path = Path(row["file_path"])
        student_id = row["student_id"]
        _process_one(file_path, student_id, rubric)

def watch_loop(rubric_path: Path, poll_interval: int = 10) -> None:
    """Continuously watch the sync folder for new files.
    New files are discovered via ``discover_new_submissions`` which also adds them
    to the SQLite tracking table. The loop then processes any rows with status
    ``new``.
    """
    print(f"[WATCH] Monitoring {ONEDRIVE_SYNC_PATH} (interval {poll_interval}s)")
    rubric = load_rubric(rubric_path)
    while True:
        # Discover any files that have appeared since the last poll.
        list(discover_new_submissions())
        # Process any pending entries.
        pending = get_pending()
        for row in pending:
            _process_one(Path(row["file_path"]), row["student_id"], rubric)
        time.sleep(poll_interval)

def main() -> None:
    parser = argparse.ArgumentParser(description="Local AI Assignment Checker CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # grade-all command
    p_all = subparsers.add_parser("grade-all", help="Batch‑process all new submissions")
    p_all.add_argument("--rubric", required=True, type=Path, help="Path to rubric YAML file")

    # watch command
    p_watch = subparsers.add_parser("watch", help="Continuously watch for new submissions")
    p_watch.add_argument("--rubric", required=True, type=Path, help="Path to rubric YAML file")
    p_watch.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")

    # eval command (optional – compare CSVs)
    p_eval = subparsers.add_parser("eval", help="Compare generated CSV with a gold‑standard CSV")
    p_eval.add_argument("--gold", required=True, type=Path, help="Path to gold‑standard CSV")
    p_eval.add_argument("--generated", default=str(OUTPUT_CSV_PATH), help="Path to generated CSV (defaults to config)")

    # map-marks command – rollno x Assign1..11 Excel joined with attendance.
    # Professor flow: everything lives in <OneDrive>/mca_labs (auto-found).
    # Attendance and output default into that same folder, so sir only
    # manages files — one command does the rest. Re-runs pick up new files.
    p_map = subparsers.add_parser("map-marks", help="Build rollno x assignment marks Excel from attendance + scanned submissions")
    p_map.add_argument("--attendance", type=Path, default=None, help="Path to attendance.xlsx (default: *attendance*.xlsx inside the subject folder)")
    p_map.add_argument("--output", type=Path, default=None, help="Output Excel path (default: marks sheet inside the subject folder)")
    p_map.add_argument("--assignments", type=int, default=11, help="Number of assignments/labs")
    p_map.add_argument("--no-grade", action="store_true", help="Skip LLM grading: Present+submitted=10, Absent+submitted=5")
    p_map.add_argument("--rubric", type=Path, default=None, help="Rubric YAML (needed unless --no-grade)")
    p_map.add_argument("--subject", default=None, help="Only grade files with this in the filename (e.g. mca)")
    p_map.add_argument("--sync-path", type=Path, default=None, help="Override the auto-detected subject folder for this run")
    p_map.add_argument("--interval", type=int, default=0, help="If >0, re-run every N seconds (auto mode) instead of once")

    args = parser.parse_args()

    if args.command == "grade-all":
        _process_pending(args.rubric)
    elif args.command == "watch":
        watch_loop(args.rubric, poll_interval=args.interval)
    elif args.command == "map-marks":
        from checker.marks_mapper import build_marks, ai_score_fn_factory, default_score_fn, find_attendance
        if args.no_grade:
            score_fn = default_score_fn
        else:
            if not args.rubric:
                parser.error("map-marks without --no-grade requires --rubric <path>")
            score_fn = ai_score_fn_factory(load_rubric(args.rubric))
        sync_path = Path(args.sync_path) if args.sync_path else ONEDRIVE_SYNC_PATH
        attendance = Path(args.attendance) if args.attendance else find_attendance(sync_path)
        if attendance is None:
            parser.error(f"No *attendance*.xlsx found in {sync_path} — pass --attendance <path>")
        if args.output:
            output = Path(args.output)
        elif args.subject:
            output = sync_path / f"marks_{args.subject.lower()}_output.xlsx"
        else:
            output = sync_path / "marks_output.xlsx"
        print(f"[MAP] folder={sync_path} attendance={attendance.name} -> {output.name}")
        if args.interval and args.interval > 0:
            print(f"[AUTO] Re-running every {args.interval}s. Ctrl+C to stop.")
            while True:
                build_marks(attendance, sync_path, output,
                            n_assignments=args.assignments, score_fn=score_fn,
                            subject=args.subject)
                time.sleep(args.interval)
        else:
            build_marks(attendance, sync_path, output,
                        n_assignments=args.assignments, score_fn=score_fn,
                        subject=args.subject)
    elif args.command == "eval":
        # Simple diff: count rows that differ.
        import csv
        def load_rows(csv_path: Path):
            with csv_path.open(newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        gold = load_rows(args.gold)
        gen = load_rows(Path(args.generated))
        mismatches = [g for g, s in zip(gold, gen) if g != s]
        print(f"[EVAL] Total rows: {len(gold)} – mismatches: {len(mismatches)}")
        for m in mismatches:
            print(m)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
