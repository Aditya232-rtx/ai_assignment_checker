# rubric.py
"""Load a grading rubric from a YAML file.
The rubric is expected to contain a top‑level ``criteria`` list, each entry
having ``name``, ``max``, and an optional ``description``.
"""
import yaml
from pathlib import Path
from typing import Dict, Any

def load_rubric(rubric_path: Path) -> Dict[str, Any]:
    """Read a YAML file and return the parsed rubric dict.
    Raises ``FileNotFoundError`` if the file does not exist and ``yaml.YAMLError``
    on syntax problems.
    """
    with rubric_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Basic validation – ensure we have a list of criteria.
    if not isinstance(data, dict) or "criteria" not in data or not isinstance(data["criteria"], list):
        raise ValueError("Rubric must be a mapping with a 'criteria' list.")
    return data
