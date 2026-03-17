from __future__ import annotations

from typing import Any, Callable

from ..adapters.llm import LlmAdapter
from ..models.runtime import RuntimeOptions
from ..models.summary import SummaryResult

QuickreadEventCallback = Callable[[str, str, dict[str, Any] | None], None]

def summarize_transcript(
    options: RuntimeOptions,
    transcript: str,
    event_callback: QuickreadEventCallback | None = None,
) -> SummaryResult:
    adapter = LlmAdapter(
        siliconflow_api_key=options.siliconflow_api_key,
        dashscope_api_key=options.dashscope_api_key,
        siliconflow_base_url=options.siliconflow_base_url,
        dashscope_base_url=options.dashscope_base_url,
        siliconflow_model=options.siliconflow_model,
        dashscope_model=options.dashscope_model,
        llm_max_chars=options.llm_max_chars,
    )
    _emit_event(event_callback, "summary_provider", "开始调用总结模型")
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
