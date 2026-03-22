from __future__ import annotations

from typing import Any, Callable

from ..adapters.llm import LlmAdapter
from ..models.runtime import RuntimeOptions
from ..models.summary import SummaryResult
from ..subsystems.summary import build_summary_prompt_config, build_summary_provider_configs

QuickreadEventCallback = Callable[[str, str, dict[str, Any] | None], None]

def summarize_transcript(
    options: RuntimeOptions,
    transcript: str,
    event_callback: QuickreadEventCallback | None = None,
) -> SummaryResult:
    summary_prompt = build_summary_prompt_config(options)
    summary_providers = build_summary_provider_configs(options)
    adapter = LlmAdapter(
        providers=summary_providers,
        llm_max_chars=options.llm_max_chars,
        summary_system_prompt=summary_prompt.system_prompt,
        summary_user_prompt=summary_prompt.user_prompt_template,
    )
    _emit_event(
        event_callback,
        "summary_provider",
        "开始调用总结模型",
        {"prompt_id": summary_prompt.prompt_id},
    )
    result = adapter.summarize(transcript)
    _emit_event(event_callback, "summary_provider_completed", "总结模型返回结果", {"provider": result.provider})
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
