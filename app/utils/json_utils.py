from __future__ import annotations

import json
import re

from ..exceptions import VividError


def to_pretty_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def extract_json_block(text: str) -> dict:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, flags=re.S)
    if fenced:
        candidate = fenced.group(1)
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        candidate = candidate[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        snippet = candidate[:240].replace("\n", "\\n")
        raise VividError(f"LLM response did not contain valid JSON: {snippet}") from exc
    if not isinstance(payload, dict):
        raise VividError("LLM response JSON must be an object.")
    return payload
