# tests/test_agents.py
import json
import pytest
from pathlib import Path
from checker.agents.grader import _build_prompt as grader_prompt, GRADE_SCHEMA
from checker.agents.verifier import _build_prompt as verifier_prompt

# Minimal dummy rubric for testing
RUBRIC = {
    "criteria": [
        {"name": "Clarity", "max": 5, "description": "How clear the text is"},
        {"name": "Correctness", "max": 10, "description": "Accuracy of answer"},
    ]
}

SUBMISSION_TEXT = "This is a short student submission that mentions clarity and correctness."

def test_grader_prompt_contains_schema():
    prompt = grader_prompt(RUBRIC, SUBMISSION_TEXT)
    # The schema should appear as a JSON string inside the prompt.
    assert json.dumps(GRADE_SCHEMA) in prompt
    assert "Clarity" in prompt and "Correctness" in prompt

def test_verifier_prompt_structure():
    dummy_grading = [
        {"criterion": "Clarity", "score": 4, "max": 5, "justification": "Good", "evidence": "clarity"},
        {"criterion": "Correctness", "score": 9, "max": 10, "justification": "Mostly right", "evidence": "correctness"},
    ]
    prompt = verifier_prompt(RUBRIC, SUBMISSION_TEXT, dummy_grading)
    # Ensure rubric, submission excerpt, and grading JSON are all present.
    assert "Rubric" in prompt
    assert "Submission" in prompt
    assert json.dumps(dummy_grading, indent=2) in prompt
    # The prompt must ask for a JSON object with confidence/adjusted/notes.
    assert "confidence" in prompt.lower()
    assert "adjusted" in prompt.lower()
    assert "notes" in prompt.lower()
