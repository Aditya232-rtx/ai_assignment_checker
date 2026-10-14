# config.py
"""Configuration for the local AI Assignment Checker pipeline.
All values can be overridden via environment variables – useful for CI or
different teacher machines.
"""
import os
import re
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env automatically
load_dotenv()

# Base directory of the project (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent

# Ollama settings – defaults to a local server.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-oss-120b")

# Cloud settings
USE_OLLAMA_CLOUD = os.getenv("USE_OLLAMA_CLOUD", "false").lower() in ["1", "true", "yes"]
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL")
OLLAMA_CLOUD_KEY = os.getenv("OLLAMA_CLOUD_KEY")

# Determine which endpoint to use
if USE_OLLAMA_CLOUD and OLLAMA_CLOUD_URL:
    OLLAMA_URL = OLLAMA_CLOUD_URL.rstrip('/')
    # OpenAI‑compatible chat endpoint. OLLAMA_CLOUD_URL may already include
    # the /v1 prefix (e.g. https://api.ollama.com/v1) — don't double it.
    if OLLAMA_URL.endswith("/v1"):
        OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_URL}/chat/completions"
    else:
        OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_URL}/v1/chat/completions"
else:
    # Local Ollama generate endpoint (fallback)
    OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_URL}/api/generate"

# Name of the subject folder inside OneDrive. Sir keeps everything here:
# student expt files + attendance.xlsx, and the pipeline writes the marks
# sheet back into the same folder. Override with MCA_LABS_NAME if needed.
MCA_LABS_NAME = os.getenv("MCA_LABS_NAME", "mca_labs")


def _norm_name(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", s.strip().lower())


def _find_subject_folder() -> Optional[Path]:
    """Auto-locate the subject folder on this machine.

    Candidate names in priority order: MCA_LABS_NAME env (only if explicitly
    set), then "MCA_TEST", then "mca_labs". For each candidate we try an
    exact name match first, then containment — OneDrive prefixes shared
    folders with the sharer ("Manoj Suryawanshi's files - MCA-TEST").
    Checks ~/OneDrive*, ~/Library/CloudStorage/OneDrive* (macOS), the home
    dir and ~/Downloads. Returns None if nothing matches.
    """
    env_name = os.getenv("MCA_LABS_NAME")
    wanted: List[str] = []
    if env_name:
        wanted.append(_norm_name(env_name))
    for name in ("mca_test", "mca_labs"):
        n = _norm_name(name)
        if n not in wanted:
            wanted.append(n)

    home = Path.home()
    roots: List[Path] = [home, home / "Library" / "CloudStorage", home / "Downloads"]

    def _iter_candidates():
        for root in roots:
            if not root.is_dir():
                continue
            try:
                entries = list(root.iterdir())
            except OSError:
                continue
            for entry in entries:
                try:
                    if entry.is_dir():
                        yield entry
                except OSError:
                    continue
            # Inside OneDrive containers (normal sync / add-shortcut path)
            for entry in entries:
                try:
                    is_od = entry.is_dir() and entry.name.lower().startswith("onedrive")
                except OSError:
                    continue
                if not is_od:
                    continue
                try:
                    for kid in entry.iterdir():
                        if kid.is_dir():
                            yield kid
                except OSError:
                    continue

    for want in wanted:
        # exact match first, then containment (prefixed shared-folder names)
        try:
            exact = [p for p in _iter_candidates() if _norm_name(p.name) == want]
        except OSError:
            exact = []
        if exact:
            return sorted(exact, key=lambda p: str(p))[0]
        try:
            loose = [p for p in _iter_candidates() if want in _norm_name(p.name)]
        except OSError:
            loose = []
        if loose:
            return sorted(loose, key=lambda p: str(p))[0]
    return None


def _default_sync_path() -> Path:
    found = _find_subject_folder()
    if found is not None:
        return found
    return BASE_DIR / "data" / "student_work"


# Path where the OneDrive sync client stores the subject folder.
# Explicit env wins (sir can set it); otherwise auto-detected; otherwise local demo.
ONEDRIVE_SYNC_PATH = Path(os.getenv("ONEDRIVE_SYNC_PATH", _default_sync_path()))

# Output CSV where the final grades will be appended.
OUTPUT_CSV_PATH = Path(os.getenv("OUTPUT_CSV_PATH", BASE_DIR / "data" / "grades_output.csv"))

# Operational flags.
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ["1", "true", "yes"]
RETAIN_RAW = os.getenv("RETAIN_RAW", "true").lower() in ["1", "true", "yes"]

# Ensure data directories exist at runtime (safe to call multiple times).
for p in (ONEDRIVE_SYNC_PATH, OUTPUT_CSV_PATH.parent):
    p.mkdir(parents=True, exist_ok=True)
