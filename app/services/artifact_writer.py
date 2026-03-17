from __future__ import annotations

import json
from pathlib import Path

from ..models.artifact import ArtifactBundle
from ..models.source import SourceInfo
from ..models.summary import SummaryResult
from ..models.transcript import TranscriptResult
from .diagnostics import build_error_summary, extract_failure_chain
from .run_state import checkpoint_path


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_artifacts(
    workdir: Path,
    source: SourceInfo,
    transcript: TranscriptResult,
    summary: SummaryResult,
    rendered: str,
    output_format: str = "both",
    diagnostics: list[dict] | None = None,
) -> ArtifactBundle:
    artifacts_dir = workdir / "artifacts"
    bundle = ArtifactBundle(
        workdir=workdir,
        artifacts_dir=artifacts_dir,
        quickread_markdown=artifacts_dir / "quickread.md",
        transcript_text=artifacts_dir / "transcript.txt",
        summary_markdown=artifacts_dir / "summary.md",
        summary_json=artifacts_dir / "summary.json",
        metadata_json=artifacts_dir / "metadata.json",
        checkpoint_json=checkpoint_path(workdir),
    )
    _write_text(bundle.quickread_markdown, rendered.rstrip() + "\n")
    _write_text(bundle.transcript_text, transcript.text.rstrip() + "\n")
    _write_text(
        bundle.summary_markdown,
        "\n".join(
            [
                "# Summary",
                "",
                summary.one_line,
                "",
                summary.detailed,
                "",
                "## Key Points",
                "",
                *[f"- {item}" for item in summary.key_points],
                "",
            ]
        ),
    )
    _write_text(
        bundle.summary_json,
        json.dumps(
            {
                "one_line": summary.one_line,
                "detailed": summary.detailed,
                "key_points": summary.key_points,
                "provider": summary.provider,
                "output_format": output_format,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write_text(
        bundle.metadata_json,
        json.dumps(
            {
                "source": source.raw_source,
                "platform": source.platform,
                "title": source.title,
                "acquisition_method": transcript.acquisition_method,
                "workdir": str(workdir),
                "media_path": str(transcript.media_path) if transcript.media_path else None,
                "audio_path": str(transcript.audio_path) if transcript.audio_path else None,
                "diagnostics": diagnostics or [],
                "failure_chain": extract_failure_chain(diagnostics or []),
                "error_summary": build_error_summary(diagnostics or []),
                "saved_files": {
                    "quickread_markdown": str(bundle.quickread_markdown),
                    "transcript_text": str(bundle.transcript_text),
                    "summary_markdown": str(bundle.summary_markdown),
                    "summary_json": str(bundle.summary_json),
                    "metadata_json": str(bundle.metadata_json),
                    "checkpoint_json": str(bundle.checkpoint_json) if bundle.checkpoint_json else None,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    return bundle
