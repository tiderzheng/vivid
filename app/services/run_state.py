from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models.calibration import CalibrationResult
from ..models.summary import SummaryResult
from ..models.transcript import TranscriptResult


def checkpoint_path(workdir: Path) -> Path:
    return workdir / "artifacts" / "run_state.json"


def load_run_state(workdir: Path) -> dict[str, Any]:
    path = checkpoint_path(workdir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_run_state(workdir: Path, payload: dict[str, Any]) -> Path:
    path = checkpoint_path(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def update_run_state(base_workdir: Path, **changes: Any) -> dict[str, Any]:
    payload = load_run_state(base_workdir)
    for key, value in changes.items():
        if value is None:
            continue
        payload[key] = value
    save_run_state(base_workdir, payload)
    return payload


def transcript_to_payload(transcript: TranscriptResult) -> dict[str, Any]:
    return {
        "text": transcript.text,
        "acquisition_method": transcript.acquisition_method,
        "media_path": str(transcript.media_path) if transcript.media_path else None,
        "audio_path": str(transcript.audio_path) if transcript.audio_path else None,
    }


def transcript_from_payload(payload: dict[str, Any]) -> TranscriptResult:
    return TranscriptResult(
        text=str(payload.get("text") or ""),
        acquisition_method=str(payload.get("acquisition_method") or "checkpoint"),
        media_path=_coerce_path(payload.get("media_path")),
        audio_path=_coerce_path(payload.get("audio_path")),
    )


def summary_to_payload(summary: SummaryResult) -> dict[str, Any]:
    return summary.to_payload()


def summary_from_payload(payload: dict[str, Any]) -> SummaryResult:
    return SummaryResult(
        title=str(payload.get("title") or payload.get("one_line") or ""),
        overview=str(payload.get("overview") or payload.get("detailed") or ""),
        core_points=[str(item) for item in payload.get("core_points", payload.get("key_points", [])) or []],
        controversies=[str(item) for item in payload.get("controversies", []) or []],
        action_suggestions=[str(item) for item in payload.get("action_suggestions", []) or []],
        playful_comment=str(payload.get("playful_comment") or ""),
        provider=str(payload.get("provider") or "checkpoint"),
    )


def calibration_to_payload(calibration: CalibrationResult) -> dict[str, Any]:
    return calibration.to_payload()


def calibration_from_payload(payload: dict[str, Any]) -> CalibrationResult:
    return CalibrationResult(
        cn_text=str(payload.get("cn_text") or ""),
        en_text=str(payload.get("en_text") or ""),
        provider=str(payload.get("provider") or "checkpoint"),
    )


def _payload_has_summary(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    return bool(_text_or_none(summary.get("overview")) or _text_or_none(summary.get("detailed")) or _text_or_none(summary.get("title")) or _text_or_none(summary.get("one_line")))


def _payload_has_calibration(calibration: dict[str, Any] | None) -> bool:
    if not isinstance(calibration, dict):
        return False
    return bool(_text_or_none(calibration.get("cn_text")) or _text_or_none(calibration.get("en_text")))


def available_resume_stages(payload: dict[str, Any]) -> list[str]:
    stages: list[str] = []
    media_path = _coerce_path(payload.get("media_path"))
    transcript = payload.get("transcript")
    summary = payload.get("summary")
    calibration = payload.get("calibration")
    rendered = payload.get("rendered")
    if media_path and media_path.exists():
        stages.append("transcription")
    if isinstance(transcript, dict) and transcript.get("text"):
        stages.append("summarize")
    if isinstance(transcript, dict) and transcript.get("text") and _payload_has_summary(summary):
        stages.append("calibrate")
    if (
        isinstance(transcript, dict)
        and transcript.get("text")
        and _payload_has_summary(summary)
        and _payload_has_calibration(calibration)
    ):
        stages.append("render")
    if (
        isinstance(transcript, dict)
        and transcript.get("text")
        and _payload_has_summary(summary)
        and _text_or_none(rendered)
    ):
        stages.append("artifacts")
    return stages


def suggested_resume_stage(payload: dict[str, Any], failed_stage: str | None = None) -> str | None:
    stages = available_resume_stages(payload)
    if failed_stage in {"summarize", "summary_provider", "summary_provider_completed", "summarize_completed"} and "summarize" in stages:
        return "summarize"
    if failed_stage in {"calibrate", "calibration_provider", "calibration_provider_completed", "calibrate_completed"} and "calibrate" in stages:
        return "calibrate"
    if failed_stage in {"render", "artifacts"}:
        if failed_stage == "render" and "render" in stages:
            return "render"
        if "artifacts" in stages:
            return "artifacts"
    if failed_stage in {"transcription", "transcription_fallback", "transcription_failed", "ocr", "ocr_fallback"} and "transcription" in stages:
        return "transcription"
    if "summarize" in stages:
        return "summarize"
    if "transcription" in stages:
        return "transcription"
    if "render" in stages:
        return "render"
    if "artifacts" in stages:
        return "artifacts"
    return None


def _coerce_path(value: Any) -> Path | None:
    text = _text_or_none(value)
    if not text:
        return None
    return Path(text).expanduser()


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
