# tests/test_cli.py
"""End-to-end CLI tests.

Safety rules (the original version violated all three):
  * run via `python -m checker.cli` (absolute imports break `python checker/cli.py`)
  * every path (sync folder, DB, CSV) lives in pytest's tmp_path — never the
    real data/ directory (the old test DELETED data/grading.db on teardown)
  * fully offline: USE_OLLAMA_CLOUD=false + unreachable OLLAMA_URL makes the
    grader/verifier fail fast into their deterministic fallbacks — no network,
    no tokens, stable assertions.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _env(tmp: dict) -> dict:
    env = dict(os.environ)
    env.update({
        "USE_OLLAMA_CLOUD": "false",
        "OLLAMA_URL": "http://127.0.0.1:1",   # nothing listens -> fast fallback
        "MODEL_NAME": "offline-test",
        **tmp,
    })
    return env


def _run(args: list, env: dict, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "checker.cli", *args],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=timeout, check=False,
    )


def _setup(tmp_path: Path) -> tuple:
    """Create isolated sync folder + rubric + CSV/DB paths. Returns (env, csv)."""
    work = tmp_path / "student_work"
    work.mkdir()
    (work / "alice_essay.txt").write_text(
        "Alice's essay about the importance of testing.", encoding="utf-8"
    )
    rubric = tmp_path / "rubric.yaml"
    rubric.write_text(
        "criteria:\n"
        "  - name: Clarity\n    max: 5\n    description: clarity\n"
        "  - name: Correctness\n    max: 10\n    description: accuracy\n",
        encoding="utf-8",
    )
    csv = tmp_path / "grades_output.csv"
    env = _env({
        "ONEDRIVE_SYNC_PATH": str(work),
        "OUTPUT_CSV_PATH": str(csv),
        "GRADING_DB_PATH": str(tmp_path / "grading.db"),
    })
    # fresh isolated DB
    subprocess.run(
        [sys.executable, "-c", "from checker.db import init_db; init_db()"],
        cwd=REPO, env=env, check=True, capture_output=True,
    )
    return env, rubric, csv


def test_grade_all_creates_csv(tmp_path: Path):
    env, rubric, csv = _setup(tmp_path)
    result = _run(["grade-all", "--rubric", str(rubric)], env)
    assert result.returncode == 0, result.stderr
    assert csv.is_file()
    lines = csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # header + one row
    header, row = lines
    assert "student_id" in header.lower()
    assert "alice" in row.lower()

    # re-run: already graded -> no duplicate row
    result2 = _run(["grade-all", "--rubric", str(rubric)], env)
    assert result2.returncode == 0
    assert len(csv.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_watch_processes_new_file(tmp_path: Path):
    env, rubric, csv = _setup(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-m", "checker.cli", "watch",
         "--rubric", str(rubric), "--interval", "1"],
        cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            if csv.is_file() and len(csv.read_text(encoding="utf-8").strip().splitlines()) >= 2:
                break
            time.sleep(0.5)
        else:
            raise AssertionError("watch did not produce a CSV row within 30s")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    assert len(csv.read_text(encoding="utf-8").strip().splitlines()) >= 2
