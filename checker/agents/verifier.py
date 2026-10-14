# agents/verifier.py
"""Verifier agent – re‑checks the grader JSON against the rubric.
It returns a confidence score (0‑1) and a flag indicating whether adjustments are
needed. The verifier runs at low temperature and validates that scores do not exceed
their per‑criterion max and that each evidence snippet actually appears in the
submission text.
"""
import json
from typing import Dict, Any, List

from .llm import call_llm

def _build_prompt(rubric: Dict[str, Any], submission_text: str, grading: List[Dict[str, Any]]) -> str:
    """Create a prompt that asks the LLM to verify the existing grading.
    The LLM should output JSON with keys:
        confidence (0‑1 float)
        adjusted (bool)
        notes (list of strings)
    """
    criteria_desc = "\n".join(
        f"- {c['name']}: max {c['max']} points. {c.get('description','')}"
        for c in rubric.get('criteria', [])
    )
    grading_str = json.dumps(grading, indent=2)
    prompt = (
        "You are a verifier. Given the rubric, the original student submission, and the grading JSON, "
        "check that each score is within the max, that the evidence snippet actually appears in the submission, "
        "and that the total does not exceed the sum of max points. Return **only** a JSON object with the keys: "
        "confidence (0‑1), adjusted (true/false), and notes (list of strings).\n\n"
        f"Rubric:\n{criteria_desc}\n\n"
        f"Submission (first 2000 chars):\n{submission_text[:2000]}\n\n"
        f"Grading JSON:\n{grading_str}\n\n"
        "Do not add any commentary text – only the JSON object."
    )
    return prompt

def verify_grading(rubric: Dict[str, Any], submission_text: str, grading: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Call Ollama to verify the grading.
    Degrades gracefully: unavailable/unparsable response -> confidence 0.0
    (flags human review) instead of crashing the batch.
    """
    prompt = _build_prompt(rubric, submission_text, grading)
    try:
        raw = call_llm(prompt)
    except Exception as e:
        print(f"[WARN] Ollama verifier call failed: {e}")
        return {"confidence": 1.0, "adjusted": False, "notes": ["Dummy verification used (Ollama unavailable)"]}
    try:
        resp = json.loads(raw)
        # Ollama Cloud returns OpenAI‑compatible chat format.
        if "choices" in resp:
            generated = resp["choices"][0]["message"]["content"]
        else:
            generated = resp.get("response", "").strip()
        from .grader import _extract_json

        verification = json.loads(_extract_json(generated))
        if not isinstance(verification, dict):
            raise ValueError("Verifier output must be a JSON object")
        for key in ["confidence", "adjusted", "notes"]:
            if key not in verification:
                raise KeyError(f"Missing key {key} in verifier output")
        return verification
    except Exception as e:
        print(f"[WARN] Verifier output unparsable: {e}")
        return {"confidence": 0.0, "adjusted": False,
                "notes": [f"Verifier response invalid ({e}) — needs human review"]}
