from __future__ import annotations

from ..models.source import SourceInfo
from ..models.summary import SummaryResult
from ..models.transcript import TranscriptResult


def render_quickread(source: SourceInfo, transcript: TranscriptResult, summary: SummaryResult, output_format: str) -> str:
    lines = [
        "========================================",
        "🎬 视频速看完成",
        "========================================",
        "",
        f"📌 来源: {source.raw_source}",
        f"📌 平台: {source.platform}",
        f"📌 标题: {source.title}",
        f"📌 获取方式: {transcript.acquisition_method}",
        f"📌 摘要引擎: {summary.provider}",
        "",
    ]
    if output_format in {"transcript", "both"}:
        lines.extend(["---------- 📝 原文逐字稿 ----------", transcript.text or "[空]", ""])
    if output_format in {"summary", "both"}:
        core_points = [f"- {item}" for item in summary.core_points] or ["- [空]"]
        controversies = [f"- {item}" for item in summary.controversies] or ["- [空]"]
        action_suggestions = [f"- {item}" for item in summary.action_suggestions] or ["- [空]"]
        lines.extend(
            [
                "---------- 📝 内容摘要 ----------",
                "",
                f"标题：{summary.title}",
                "",
                "内容概览",
                summary.overview or "[空]",
                "",
                "核心观点",
                *core_points,
                "",
                "争议点",
                *controversies,
                "",
                "行动建议",
                *action_suggestions,
                "",
                "俏皮点评",
                summary.playful_comment or "[空]",
                "",
            ]
        )
    lines.append("========================================")
    return "\n".join(lines).strip() + "\n"
