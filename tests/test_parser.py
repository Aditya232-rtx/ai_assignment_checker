import pytest
from pathlib import Path
from checker.parser import parse_file

def test_parse_txt(tmp_path: Path):
    f = tmp_path / "bob.txt"
    f.write_text("Hello world", encoding="utf-8")
    text, mime = parse_file(f)
    assert mime == "txt"
    assert "Hello" in text

def test_parse_code(tmp_path: Path):
    f = tmp_path / "code.py"
    f.write_text("print('hi')", encoding="utf-8")
    text, mime = parse_file(f)
    assert mime == "code"
    assert "print" in text
