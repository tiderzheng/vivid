from __future__ import annotations

import json
import sys
from typing import Any


def log(message: str) -> None:
    print(message, file=sys.stderr)


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **_clean_fields(fields)}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)


def log_exception(event: str, exc: BaseException, **fields: Any) -> None:
    payload = {
        "event": event,
        "error_type": exc.__class__.__name__,
        "error": str(exc),
        **_clean_fields(fields),
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)


def _clean_fields(fields: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        cleaned[key] = value
    return cleaned
