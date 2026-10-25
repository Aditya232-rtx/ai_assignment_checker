"""Small local web UI for the assignment checker.

The server intentionally uses only Python's standard library. It exposes a
thin JSON API over the existing marks mapper instead of duplicating grading
logic in the frontend.
"""
from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import BASE_DIR, MODEL_NAME, ONEDRIVE_SYNC_PATH

WEB_DIR = Path(__file__).resolve().parent / "web"


def _path(value: str | None, default: Path) -> Path:
    candidate = Path(value).expanduser() if value else default
    return candidate if candidate.is_absolute() else (BASE_DIR / candidate).resolve()


def _default_payload() -> dict:
    return {
        "folder": str(ONEDRIVE_SYNC_PATH),
        "attendance": "",
        "rubric": str(BASE_DIR / "rubrics" / "example_rubric.yaml"),
        "assignments": 11,
        "no_grade": False,
    }


def inspect_folder(payload: dict) -> dict:
    from .marks_mapper import find_attendance, load_attendance, scan_submissions

    folder = _path(payload.get("folder"), ONEDRIVE_SYNC_PATH)
    assignments = max(1, min(99, int(payload.get("assignments", 11))))
    if not folder.is_dir():
        raise ValueError(f"Folder does not exist: {folder}")
    attendance = _path(payload.get("attendance"), find_attendance(folder) or folder / "attendance.xlsx")
    output = folder / "marks_output.xlsx"
    submissions, unmapped = scan_submissions(
        folder,
        assignments,
        exclude=[output, output.with_suffix(".txt")],
    )
    students = set(roll for roll, _ in submissions)
    attendance_rows = 0
    attendance_rolls = set()
    if attendance.is_file():
        attendance_rolls = set(load_attendance(attendance, assignments)[0])
        attendance_rows = len(attendance_rolls)
    # Match build_marks: tracked students are the union of the attendance
    # roster and any student who submitted work but is missing from it.
    tracked_students = attendance_rolls | students
    return {
        "folder": str(folder),
        "attendance": str(attendance) if attendance.is_file() else None,
        "mapped_submissions": len(submissions),
        "unmapped_files": len(unmapped),
        "students": len(tracked_students),
        "attendance_rows": attendance_rows,
        "unmapped": unmapped[:20],
    }


def run_marks(payload: dict) -> dict:
    from .marks_mapper import (
        ai_score_fn_factory,
        build_marks,
        default_score_fn,
        find_attendance,
        rubric_signature,
    )
    from .rubric import load_rubric

    folder = _path(payload.get("folder"), ONEDRIVE_SYNC_PATH)
    if not folder.is_dir():
        raise ValueError(f"Folder does not exist: {folder}")
    assignments = max(1, min(99, int(payload.get("assignments", 11))))
    attendance = _path(payload.get("attendance"), find_attendance(folder) or folder / "attendance.xlsx")
    if not attendance.is_file():
        raise ValueError(f"Attendance workbook not found: {attendance}")
    output = _path(payload.get("output"), folder / "marks_output.xlsx")
    no_grade = bool(payload.get("no_grade"))
    if no_grade:
        score_fn = default_score_fn
        grade_meta = "nograde"
    else:
        rubric_path = _path(payload.get("rubric"), BASE_DIR / "rubrics" / "example_rubric.yaml")
        rubric = load_rubric(rubric_path)
        score_fn = ai_score_fn_factory(rubric)
        grade_meta = f"model={MODEL_NAME}|rubric={rubric_signature(rubric)}"

    df = build_marks(
        attendance,
        folder,
        output,
        n_assignments=assignments,
        score_fn=score_fn,
        subject=payload.get("subject") or None,
        grade_meta=grade_meta,
    )
    records = json.loads(df.to_json(orient="records"))
    return {
        "output": str(output),
        "report": str(output.with_suffix(".txt")),
        "rows": records,
        "students": len(records),
        "assignments": assignments,
        "total_marks": round(float(df["Total"].sum()), 2) if not df.empty else 0,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AssignmentChecker/1.0"

    def log_message(self, fmt: str, *args) -> None:
        # Keep the terminal useful: only API errors and startup are printed.
        if self.path.startswith("/api/") and self.command != "GET":
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, default=str).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/defaults":
            self._json(HTTPStatus.OK, _default_payload())
            return
        if parsed.path == "/api/inspect":
            params = parse_qs(parsed.query)
            payload = {key: values[-1] for key, values in params.items()}
            try:
                self._json(HTTPStatus.OK, {"ok": True, **inspect_folder(payload)})
            except Exception as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/file":
            requested = parse_qs(parsed.query).get("path", [""])[-1]
            candidate = Path(requested).expanduser().resolve()
            if not candidate.is_file():
                self._send(HTTPStatus.NOT_FOUND, b"File not found", "text/plain")
                return
            try:
                self._send(HTTPStatus.OK, candidate.read_bytes(), mimetypes.guess_type(candidate.name)[0] or "text/plain")
            except OSError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/run":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = run_marks(payload)
            self._json(HTTPStatus.OK, {"ok": True, **result})
        except Exception as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})

    def _serve_static(self, request_path: str) -> None:
        relative = request_path.lstrip("/") or "index.html"
        candidate = (WEB_DIR / relative).resolve()
        if WEB_DIR not in candidate.parents and candidate != WEB_DIR:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
            return
        if not candidate.is_file():
            candidate = WEB_DIR / "index.html"
        try:
            self._send(HTTPStatus.OK, candidate.read_bytes(), mimetypes.guess_type(candidate.name)[0] or "text/plain")
        except OSError:
            self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")


def run_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"[WEB] Assignment Checker is running at {url}")
    print("[WEB] Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WEB] Stopped.")
    finally:
        server.server_close()
