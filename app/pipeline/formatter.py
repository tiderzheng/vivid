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
        lines.extend(
            [
                "---------- 📝 内容摘要 ----------",
                "",
                summary.one_line,
                "",
                summary.detailed,
                "",
                "---------- 🔑 关键要点 ----------",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in summary.key_points)
        lines.append("")
    lines.append("========================================")
    return "\n".join(lines).strip() + "\n"
