# parser.py
"""Deterministic parsers for PDF, DOCX, TXT, and generic source files.
No LLM is used – the functions return raw Unicode text.
"""
import subprocess
from pathlib import Path
from typing import Tuple

# NOTE: `pdftotext` (poppler) and `docx2txt` must be installed on the host system.
# If they are missing, the helper will raise a clear error.

def _run_cmd(cmd: str) -> str:
    """Run a shell command and return stdout as a string.
    Raises `subprocess.CalledProcessError` on failure.
    """
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
    return result.stdout

def parse_pdf(path: Path) -> str:
    """Extract text from a PDF using the `pdftotext` CLI.
    Returns a plain‑text string preserving page breaks.
    """
    # `-layout` tries to keep the original column layout.
    return _run_cmd(f"pdftotext -layout {path!s} -")

def parse_docx(path: Path) -> str:
    """Extract text from a DOCX using `docx2txt`.
    `docx2txt` writes the output to stdout when `-` is used as the destination.
    """
    return _run_cmd(f"docx2txt {path!s} -")

def parse_txt(path: Path) -> str:
    """Read a plain‑text file (UTF‑8)."""
    return path.read_text(encoding="utf-8")

def parse_code(path: Path) -> str:
    """Return the raw source code as text. For now we treat it the same as plain‑text.
    """
    return path.read_text(encoding="utf-8")

def parse_file(file_path: Path) -> Tuple[str, str]:
    """Detect file type by extension and dispatch to the appropriate parser.
    Returns a tuple ``(text, mime)`` where ``mime`` is a short identifier such as
    ``pdf``, ``docx``, ``txt`` or ``code``.
    """
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(file_path), "pdf"
    if ext == ".docx":
        return parse_docx(file_path), "docx"
    if ext in {".txt", ".md"}:
        return parse_txt(file_path), "txt"
    # Treat any other extension as source code – we don't try to compile it.
    return parse_code(file_path), "code"
