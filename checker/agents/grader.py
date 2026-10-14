# agents/grader.py
"""Grader agent – calls Ollama to evaluate a submission against a rubric.
The agent must return **strict JSON** adhering to the grading schema.
If the LLM output cannot be parsed or fails validation, the call is retried
once with the same prompt (low temperature).  After the second failure a
RuntimeError is raised.
"""
import json
import re
from typing import List, Dict, Any

from .llm import call_llm

# JSON schema for a single grade entry.
GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "criterion": {"type": "string"},
        "score": {"type": "number"},
        "max": {"type": "number"},
        "justification": {"type": "string"},
        "evidence": {"type": "string"},
    },
    "required": ["criterion", "score", "max", "justification", "evidence"],
    "additionalProperties": False,
}

def _extract_json(s: str) -> str:
    """Strip markdown code fences (```json ... ```) models love to add."""
    s = (s or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s

def _validate_grade_entry(entry: Dict[str, Any]) -> None:
    """Validate a single grade dict against GRADE_SCHEMA using jsonschema.
    Raises jsonschema.ValidationError on failure.
    """
    try:
        import jsonschema  # Imported lazily to keep the runtime optional.
    except ImportError as e:
        raise RuntimeError("jsonschema package is required for grading schema validation") from e
    jsonschema.validate(instance=entry, schema=GRADE_SCHEMA)

def _build_prompt(rubric: Dict[str, Any], submission_text: str) -> str:
    """Create a concise prompt describing the rubric and the submission.
    The LLM is asked explicitly *only* to produce JSON matching the schema.
    """
    criteria_desc = "\n".join(
        f"- {c['name']}: max {c['max']} points. {c.get('description','')}"
        for c in rubric.get('criteria', [])
    )
    # Insert the JSON schema as a literal string.
    schema_str = json.dumps(GRADE_SCHEMA)
    prompt = (
        f"You are an academic grader. Evaluate the following student submission "
        f"against the rubric criteria below. Return **only** a JSON array where each "
        f"element matches this schema: {schema_str}. Do not include any extra text.\n\n"
        f"Rubric:\n{criteria_desc}\n\n"
        f"Student submission (first 2000 characters):\n{submission_text[:2000]}\n\n"
        f"Provide a JSON array with one entry per rubric criterion."
    )
    return prompt

def grade_submission(rubric: Dict[str, Any], submission_text: str) -> List[Dict[str, Any]]:
    """Call Ollama to obtain a grading JSON list.
    If Ollama is unavailable, fall back to a deterministic dummy grading (full points).
    """
    prompt = _build_prompt(rubric, submission_text)
    attempts = 0
    raw = ""
    while attempts < 2:
        attempts += 1
        try:
            raw = call_llm(prompt)
        except Exception as e:
            print(f"[WARN] Ollama call failed on attempt {attempts}: {e}")
            break
        try:
            resp = json.loads(raw)
            # Ollama Cloud returns OpenAI‑compatible chat format.
            if 'choices' in resp:
                generated = resp['choices'][0]['message']['content']
            else:
                # Fallback to legacy generate format.
                generated = resp.get('response', '').strip()
            grading = json.loads(_extract_json(generated))
            if not isinstance(grading, list):
                raise ValueError("Grader output must be a JSON list")
            for entry in grading:
                _validate_grade_entry(entry)
            return grading
        except Exception as e:
            if attempts >= 2:
                raise RuntimeError(f"Grader failed after {attempts} attempts: {e}\nRaw response: {raw}")
            # otherwise retry silently
            continue
    # ----------------------------------------------------------
    # Dummy fallback – give each rubric criterion its max points.
    dummy = []
    for crit in rubric.get('criteria', []):
        name = crit.get('name', 'unknown')
        max_pts = crit.get('max', 0)
        dummy.append({
            'criterion': name,
            'score': max_pts,
            'max': max_pts,
            'justification': 'Auto‑graded fallback (Ollama unavailable)',
            'evidence': 'N/A',
        })
    print('[INFO] Using dummy grading fallback.')
    return dummy
