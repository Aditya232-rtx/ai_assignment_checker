# tests/test_config.py
"""Folder discovery: the CLI takes ANY subject folder name (MCA_LABS,
PYTHON_ASSIGNMENTS, MCA-TEST, ...). Matching must be forgiving and must not
fuzzy-match absurdly short names."""
from pathlib import Path

from checker.config import find_folder


def _fake_home(tmp_path: Path) -> Path:
    """OneDrive-style layout under a temp HOME."""
    od = tmp_path / "Library" / "CloudStorage" / "OneDrive - Vidyalankar"
    (od / "PYTHON_ASSIGNMENTS").mkdir(parents=True)
    (od / "Prof Sharma's files - MCA_LABS").mkdir(parents=True)
    (tmp_path / "Downloads").mkdir()
    (tmp_path / "Downloads" / "Exam Papers").mkdir()
    return tmp_path


def test_find_folder_exact_name(tmp_path: Path, monkeypatch):
    home = _fake_home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    found = find_folder("PYTHON_ASSIGNMENTS")
    assert found == home / "Library" / "CloudStorage" / "OneDrive - Vidyalankar" / "PYTHON_ASSIGNMENTS"


def test_find_folder_forgiving_matching(tmp_path: Path, monkeypatch):
    """case / spaces / underscores / hyphens are all equivalent."""
    home = _fake_home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    expect = home / "Library" / "CloudStorage" / "OneDrive - Vidyalankar" / "PYTHON_ASSIGNMENTS"
    assert find_folder("python assignments") == expect
    assert find_folder("python_assignments") == expect
    assert find_folder("PYTHON-ASSIGNMENTS") == expect


def test_find_folder_shared_folder_containment(tmp_path: Path, monkeypatch):
    """OneDrive prefixes shared folders with the sharer — the tail name still matches."""
    home = _fake_home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    expect = home / "Library" / "CloudStorage" / "OneDrive - Vidyalankar" / "Prof Sharma's files - MCA_LABS"
    assert find_folder("MCA_LABS") == expect
    assert find_folder("mca-labs") == expect


def test_find_folder_missing_and_short_names(tmp_path: Path, monkeypatch):
    home = _fake_home(tmp_path)
    monkeypatch.setenv("HOME", str(home))
    assert find_folder("DOES_NOT_EXIST") is None
    # 1-2 char names: exact only — "ex" must NOT match "Exam Papers"
    assert find_folder("ex") is None
    assert find_folder("") is None
