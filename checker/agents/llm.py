# agents/llm.py
"""Shared Ollama LLM call helper (local or cloud) using httpx — no shell.

The previous implementation shelled out to curl with the JSON payload in
single quotes, which broke as soon as a student submission contained an
apostrophe (extremely common in essays). httpx keeps everything in-process.
"""
import json
from typing import Dict, Any

from ..config import MODEL_NAME, USE_OLLAMA_CLOUD, OLLAMA_CLOUD_KEY, OLLAMA_CHAT_ENDPOINT


def call_llm(prompt: str, temperature: float = 0.0, timeout: float = 300.0) -> str:
    """POST the prompt to Ollama (cloud OpenAI-compatible or local generate).
    Returns the raw response body as text. Raises httpx.HTTPError on failures.
    """
    import httpx

    if USE_OLLAMA_CLOUD:
        payload: Dict[str, Any] = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
    else:
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
        }
    headers = {"Content-Type": "application/json"}
    if USE_OLLAMA_CLOUD and OLLAMA_CLOUD_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_CLOUD_KEY}"
    resp = httpx.post(OLLAMA_CHAT_ENDPOINT, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text
