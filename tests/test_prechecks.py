import pytest
import hashlib
from pathlib import Path
from checker.prechecks import is_empty, is_allowed_format, compute_hash, similarity_fingerprint, run_prechecks

def test_is_empty(tmp_path: Path):
    empty_file = tmp_path / "empty.txt"
    empty_file.touch()
    assert is_empty(empty_file) is True

def test_is_allowed_format(tmp_path: Path):
    f = tmp_path / "doc.pdf"
    f.touch()
    assert is_allowed_format(f) is True
    f2 = tmp_path / "image.png"
    f2.touch()
    assert is_allowed_format(f2) is False

def test_compute_hash(tmp_path: Path):
    f = tmp_path / "data.txt"
    f.write_text("abc", encoding="utf-8")
    h = compute_hash(f)
    assert h == hashlib.sha256(b"abc").hexdigest()

def test_similarity_fingerprint():
    fp = similarity_fingerprint("some text")
    assert isinstance(fp, str) and len(fp) == 8

def test_run_prechecks(tmp_path: Path):
    f = tmp_path / "good.txt"
    f.write_text("content", encoding="utf-8")
    passed, msgs = run_prechecks(f)
    assert passed is True and not msgs
    # empty file fails
    empty = tmp_path / "empty.txt"
    empty.touch()
    passed, msgs = run_prechecks(empty)
    assert passed is False and "File is empty" in msgs[0]
