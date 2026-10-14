# tests/test_marks_mapper.py
from pathlib import Path
import pandas as pd

from checker.marks_mapper import (
    extract_rollno,
    extract_assign_no,
    scan_submissions,
    build_marks,
)


def test_extract_rollno_content_first():
    # content has roll, filename is random
    assert extract_rollno("Roll No: 24108A0004 did assignment", "random_notes.txt") == "24108A0004"
    # jumbled: assign first then roll in filename
    assert extract_rollno("", "assign2_24108A0005_report.txt") == "24108A0005"
    # only roll in filename
    assert extract_rollno("no roll here", "24108A0006_onlyroll.txt") == "24108A0006"
    # nothing -> None
    assert extract_rollno("hello world", "mystery.txt") is None


def test_extract_assign_no_variants():
    assert extract_assign_no("Assignment No: 3", "x.txt") == 3
    assert extract_assign_no("Lab 4 experiment", "x.txt") == 4
    assert extract_assign_no("ASSIGNMENT_5 done", "x.txt") == 5
    assert extract_assign_no("", "assign2_24108A0005_report.txt") == 2
    assert extract_assign_no("hello", "mystery.txt") is None
    assert extract_assign_no("Assignment 99", "x.txt") is None  # out of 1..11


def test_extract_assign_no_lab_filename_fallbacks():
    # terse lab/assign forms live in the filename, content has no identifiers
    assert extract_assign_no("some essay", "Lab7_24108A0015.pdf") == 7
    assert extract_assign_no("some essay", "lab-8-24108A0016.docx") == 8
    assert extract_assign_no("some essay", "24108A0017 LAB 9.pdf") == 9
    assert extract_assign_no("some essay", "L3_24108A0021.pdf") == 3
    assert extract_assign_no("some essay", "A5_24108A0022.docx") == 5
    assert extract_assign_no("some essay", "Exp6_24108A0023.pdf") == 6
    assert extract_assign_no("some essay", "24108A0021_3.pdf") == 3  # bare number
    # guards: rollno digits, years and v2 must NOT become assignment numbers
    assert extract_assign_no("some essay", "24108A0022.pdf") is None
    assert extract_assign_no("some essay", "report_2024_24108A0022.pdf") is None
    assert extract_assign_no("print('hi')", "bob_code_v2.py") is None


def test_build_marks_10_5_0_rule(tmp_path: Path):
    # attendance: 2 students, 3 labs
    att = pd.DataFrame([
        {"rollno": "24108A0004", "lab1": "P", "lab2": "P", "lab3": "P"},
        {"rollno": "24108A0005", "lab1": "P", "lab2": "A", "lab3": "P"},
    ])
    att_path = tmp_path / "att.xlsx"
    att.to_excel(att_path, index=False)

    # submissions: 0004 submits lab1 (present->10), 0005 submits lab2 (absent->5)
    sub = tmp_path / "work"
    sub.mkdir()
    (sub / "rand1.txt").write_text("Roll No 24108A0004 Assignment 1 solution", encoding="utf-8")
    (sub / "assign2_24108A0005.txt").write_text("my work", encoding="utf-8")  # assign from filename
    (sub / "junk.txt").write_text("no identifiers here", encoding="utf-8")

    out = tmp_path / "marks.xlsx"
    df = build_marks(att_path, sub, out, n_assignments=3)

    assert out.is_file()
    r4 = df[df["rollno"] == "24108A0004"].iloc[0]
    r5 = df[df["rollno"] == "24108A0005"].iloc[0]
    assert r4["Assign1"] == 10  # present + submitted
    assert r4["Assign2"] == 0   # not submitted
    assert r5["Assign2"] == 5   # absent + submitted -> capped 5
    assert r5["Assign1"] == 0   # not submitted

    # reasoning .txt report next to the xlsx explains every mark
    report = out.with_suffix(".txt")
    assert report.is_file()
    content = report.read_text(encoding="utf-8")
    assert "MARKING RULE" in content
    assert "[24108A0004 | Expt 1]" in content and "Present" in content
    assert "mark = AI raw score = 10.00" in content
    assert "[24108A0005 | Expt 2]" in content and "Absent" in content
    assert "caps mark at 5" in content
    assert "24108A0004: no submission file found for Expt 2, Expt 3" in content
    assert "SKIPPED FILES" in content and "junk.txt" in content


def test_ai_score_fn_returns_reasoning(monkeypatch):
    """AI scorer must return (score, reasoning) so the report can explain marks."""
    from checker import marks_mapper

    fake_grading = [
        {"criterion": "Clarity", "score": 4, "max": 5,
         "justification": "Well structured.", "evidence": "headings"},
        {"criterion": "Correctness", "score": 9, "max": 10,
         "justification": "Logic correct.", "evidence": "MOV P1"},
    ]
    monkeypatch.setattr(
        "checker.agents.grader.grade_submission", lambda rubric, text: fake_grading
    )
    fn = marks_mapper.ai_score_fn_factory({"criteria": []})
    score, reasoning = fn(Path("x.pdf"), "text", 1)
    assert score == 8.67  # (4+9)/(5+10)*10
    assert "Clarity: 4/5" in reasoning
    assert "Well structured." in reasoning
    assert "evidence: MOV P1" in reasoning
    assert "raw 8.67/10" in reasoning


def test_attendance_0_2_numeric_codes(tmp_path: Path):
    """Professor's sheet: 0 = absent, 2 = present (and fuzzy lab columns)."""
    from checker.marks_mapper import _norm_attendance_val, load_attendance

    # numeric codes
    assert _norm_attendance_val("0") == "A"
    assert _norm_attendance_val("2") == "P"
    assert _norm_attendance_val(0) == "A"     # raw int from Excel
    assert _norm_attendance_val(2) == "P"
    assert _norm_attendance_val("0.0") == "A" # Excel float cells
    assert _norm_attendance_val("2.0") == "P"
    assert _norm_attendance_val("P") == "P"
    assert _norm_attendance_val("A") == "A"

    # fuzzy columns: Roll No + Experiment headers + bare numeric headers
    att = pd.DataFrame([
        {"Roll No": "24108A0004", "Experiment 1": 2, "2": 0, "Lab3": "2"},
    ])
    path = tmp_path / "att.xlsx"
    att.to_excel(path, index=False)
    order, data = load_attendance(path, n_assignments=3)
    assert order == ["24108A0004"]
    assert data["24108A0004"] == {1: "P", 2: "A", 3: "P"}
