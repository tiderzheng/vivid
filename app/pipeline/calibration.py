from __future__ import annotations

from typing import Any, Callable

from ..adapters.llm import LlmAdapter, fallback_calibration
from ..models.calibration import CalibrationResult
from ..models.runtime import RuntimeOptions
from ..subsystems.summary.resolver import (
    build_calibration_prompt_configs,
    build_summary_provider_configs,
)

QuickreadEventCallback = Callable[[str, str, dict[str, Any] | None], None]


def calibrate_transcript(
    options: RuntimeOptions,
    transcript: str,
    event_callback: QuickreadEventCallback | None = None,
    resume_cn_text: str | None = None,
    checkpoint_callback: Callable[[dict[str, Any]], None] | None = None,
) -> CalibrationResult:
    cn_prompt, en_prompt = build_calibration_prompt_configs(options)
    providers = build_summary_provider_configs(options)
    adapter = LlmAdapter(
        providers=providers,
        llm_max_chars=options.llm_max_chars,
        summary_system_prompt="",
        summary_user_prompt="",
    )

    cn_text = resume_cn_text
    if cn_text is None:
        _emit_event(event_callback, "calibration_cn_provider", "开始调用校准模型（中文）", {"prompt_id": cn_prompt.prompt_id})
        try:
            cn_text = adapter.request_text(
                system_prompt=cn_prompt.system_prompt,
                user_prompt_template=cn_prompt.user_prompt_template,
                transcript=transcript,
            )
        except Exception:
            _emit_event(event_callback, "calibration_failed", "校准文本生成失败，跳过校准")
            return fallback_calibration(transcript)
        if checkpoint_callback is not None:
            checkpoint_callback({"calibration_cn_text": cn_text})

    _emit_event(event_callback, "calibration_cn_completed", "中文校准完成")

    _emit_event(event_callback, "calibration_en_provider", "开始调用校准模型（英文）", {"prompt_id": en_prompt.prompt_id})
    try:
        en_text = adapter.request_text(
            system_prompt=en_prompt.system_prompt,
            user_prompt_template=en_prompt.user_prompt_template,
            transcript=transcript,
        )
    except Exception:
        en_text = ""

    _emit_event(event_callback, "calibration_en_completed", "英文校准完成")
    result = CalibrationResult(cn_text=cn_text, en_text=en_text, provider=providers[0].provider_name if providers else "unknown")
    _emit_event(event_callback, "calibration_provider_completed", "校准模型返回结果", {"provider": result.provider})
    return result


def _emit_event(
    callback: QuickreadEventCallback | None,
    stage: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    if callback is None:
        return
    callback(stage, message, data or None)