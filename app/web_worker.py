from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .config import Settings
from .pipeline.orchestrator import OrchestratorResult, run_quickread
from .runtime_factory import build_runtime_options
from .services.diagnostics import build_error_summary, extract_failure_chain

PATH_SETTING_FIELDS = {
    "repo_root",
    "tools_root",
    "data_dir",
    "whisper_root",
    "transcription_output_dir",
    "bili_script",
    "douyin_script",
    "vision_api_configs_path",
    "vision_prompts_path",
    "transcription_presets_path",
    "summary_prompts_path",
    "summary_providers_path",
    "calibration_prompts_path",
}


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if len(args) != 3:
        sys.stderr.write("usage: python -m app.web_worker <input.json> <events.jsonl> <result.json>\n")
        return 2

    input_path = Path(args[0]).expanduser()
    events_path = Path(args[1]).expanduser()
    result_path = Path(args[2]).expanduser()
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        _delete_file_quietly(input_path)
        settings = _settings_from_payload(payload.get("settings") or {})
        _apply_secret_env(settings)
        values = dict(payload.get("values") or {})
        _apply_secret_values(values)

        def event_callback(stage: str, message: str, data: dict[str, Any] | None = None) -> None:
            _append_event(events_path, stage, message, data)

        options = build_runtime_options(settings, values)
        result = run_quickread(options, event_callback=event_callback)
        _write_json(result_path, {"ok": True, "result": _serialize_result(result)})
        return 0
    except BaseException as exc:  # noqa: BLE001
        _write_json(
            result_path,
            {
                "ok": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return 1


def _settings_from_payload(payload: dict[str, Any]) -> Settings:
    values = dict(payload)
    for key in PATH_SETTING_FIELDS:
        value = values.get(key)
        if value not in {None, ""}:
            values[key] = Path(str(value)).expanduser()
        else:
            values[key] = None
    return Settings(**values)


def _apply_secret_env(settings: Settings) -> None:
    settings.bili_cookie = _env_text("VIVID_WORKER_BILI_COOKIE")
    settings.sessdata = _env_text("VIVID_WORKER_SESSDATA")
    settings.siliconflow_api_key = _env_text("VIVID_WORKER_SUMMARY_API_KEY")
    settings.vision_api_key = _env_text("VIVID_WORKER_VISION_API_KEY")
    settings.dashscope_api_key = _env_text("VIVID_WORKER_DASHSCOPE_API_KEY")


def _apply_secret_values(values: dict[str, Any]) -> None:
    for key, env_name in {
        "bili_cookie": "VIVID_WORKER_BILI_COOKIE",
        "sessdata": "VIVID_WORKER_SESSDATA",
        "summary_api_key": "VIVID_WORKER_SUMMARY_API_KEY",
        "vision_api_key": "VIVID_WORKER_VISION_API_KEY",
    }.items():
        value = _env_text(env_name)
        if value:
            values[key] = value


def _env_text(name: str) -> str | None:
    return (os.environ.get(name) or "").strip() or None


def _delete_file_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


def _append_event(events_path: Path, stage: str, message: str, data: dict[str, Any] | None = None) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "message": message,
        "data": _jsonable_value(data) if data else None,
    }
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()


def _serialize_result(result: OrchestratorResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["files"] = {
        "workdir": str(result.artifacts.workdir),
        "artifacts_dir": str(result.artifacts.artifacts_dir),
        "quickread_markdown": str(result.artifacts.quickread_markdown),
        "transcript_text": str(result.artifacts.transcript_text),
        "vector_source_dir": str(result.artifacts.vector_source_dir) if result.artifacts.vector_source_dir else None,
        "vector_document_json": str(result.artifacts.vector_document_json) if result.artifacts.vector_document_json else None,
        "vector_chunks_jsonl": str(result.artifacts.vector_chunks_jsonl) if result.artifacts.vector_chunks_jsonl else None,
        "vector_manifest_json": str(result.artifacts.vector_manifest_json) if result.artifacts.vector_manifest_json else None,
        "summary_markdown": str(result.artifacts.summary_markdown),
        "summary_json": str(result.artifacts.summary_json),
        "metadata_json": str(result.artifacts.metadata_json),
        "checkpoint_json": str(result.artifacts.checkpoint_json) if result.artifacts.checkpoint_json else None,
        "calibrated_cn_markdown": str(result.artifacts.calibrated_cn_markdown)
        if result.artifacts.calibrated_cn_markdown
        else None,
        "calibrated_en_markdown": str(result.artifacts.calibrated_en_markdown)
        if result.artifacts.calibrated_en_markdown
        else None,
    }
    payload["diagnostics"] = result.diagnostics
    payload["failure_chain"] = extract_failure_chain(result.diagnostics)
    payload["error_summary"] = build_error_summary(result.diagnostics)
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable_value(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable_value(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable_value(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
