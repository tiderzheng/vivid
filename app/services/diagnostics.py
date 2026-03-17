from __future__ import annotations

from datetime import datetime
from typing import Any


FAILURE_LIKE_STAGES = {
    "subtitle_failed",
    "ocr_failed",
    "ocr_fallback",
    "transcription_failed",
    "transcription_fallback",
    "summary_provider_failed",
    "failed",
}


def build_diagnostic_event(stage: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "message": message,
        "data": data or None,
    }


def extract_failure_chain(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    for event in events or []:
        stage = str(event.get("stage") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else None
        has_error = bool((data or {}).get("error"))
        if stage not in FAILURE_LIKE_STAGES and not has_error and "fallback" not in stage and "failed" not in stage:
            continue
        chain.append(
            {
                "timestamp": event.get("timestamp"),
                "stage": stage,
                "message": event.get("message"),
                "error": (data or {}).get("error"),
                "data": data or None,
            }
        )
    return chain


def build_error_summary(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    chain = extract_failure_chain(events)
    if not chain:
        return {"has_issues": False, "headline": "", "items": []}
    items: list[str] = []
    seen: set[str] = set()
    for item in chain:
        line = _format_summary_item(item)
        if line in seen:
            continue
        seen.add(line)
        items.append(line)
    headline = f"本次任务出现 {len(items)} 个失败/回退节点"
    return {
        "has_issues": True,
        "headline": headline,
        "items": items,
    }


def _format_summary_item(item: dict[str, Any]) -> str:
    message = str(item.get("message") or item.get("stage") or "").strip()
    error = str(item.get("error") or "").strip()
    if error:
        return f"{message}：{error}"
    return message
