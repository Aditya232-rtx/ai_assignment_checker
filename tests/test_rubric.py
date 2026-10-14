import pytest
import yaml
from pathlib import Path
from checker.rubric import load_rubric

def test_load_rubric(tmp_path: Path):
    rubric_file = tmp_path / "rubric.yaml"
    rubric_file.write_text(
        """
criteria:
  - name: Clarity
    max: 5
    description: How clearly the argument is presented
  - name: Correctness
    max: 10
    description: Accuracy of the solution
        """,
        encoding="utf-8",
    )
    rubric = load_rubric(rubric_file)
    assert isinstance(rubric, dict)
    assert len(rubric["criteria"]) == 2
    assert rubric["criteria"][0]["name"] == "Clarity"
