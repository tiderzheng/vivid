from __future__ import annotations

import json
from pathlib import Path

from ..models.artifact import ArtifactBundle
from ..models.calibration import CalibrationResult
from ..models.source import SourceInfo
from ..models.summary import SummaryResult
from ..models.transcript import TranscriptResult
from .diagnostics import build_error_summary, extract_failure_chain
from .run_state import checkpoint_path
from .vector_source_writer import write_vector_source_bundle


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
    calibration: CalibrationResult | None = None,
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
        calibrated_cn_markdown=artifacts_dir / "calibrated_cn.md",
        calibrated_en_markdown=artifacts_dir / "calibrated_en.md",
    )
    vector_paths = write_vector_source_bundle(workdir, source, transcript, summary, artifacts_dir, calibration=calibration)
    bundle.vector_source_dir = vector_paths["vector_source_dir"]
    bundle.vector_document_json = vector_paths["vector_document_json"]
    bundle.vector_chunks_jsonl = vector_paths["vector_chunks_jsonl"]
    bundle.vector_manifest_json = vector_paths["vector_manifest_json"]
    _write_text(bundle.quickread_markdown, rendered.rstrip() + "\n")
    _write_text(bundle.transcript_text, transcript.text.rstrip() + "\n")
    if calibration is not None:
        _write_text(bundle.calibrated_cn_markdown, calibration.cn_text.rstrip() + "\n")
        _write_text(bundle.calibrated_en_markdown, calibration.en_text.rstrip() + "\n")
    _write_text(
        bundle.summary_markdown,
        "\n".join(
            [
                "# Summary",
                "",
                "## 标题",
                "",
                summary.title or "[空]",
                "",
                "## 内容概览",
                "",
                summary.overview or "[空]",
                "",
                "## 核心观点",
                "",
                *([f"- {item}" for item in summary.core_points] or ["- [空]"]),
                "",
                "## 争议点",
                "",
                *([f"- {item}" for item in summary.controversies] or ["- [空]"]),
                "",
                "## 行动建议",
                "",
                *([f"- {item}" for item in summary.action_suggestions] or ["- [空]"]),
                "",
                "## 俏皮点评",
                "",
                summary.playful_comment or "[空]",
                "",
            ]
        ),
    )
    _write_text(
        bundle.summary_json,
        json.dumps(
            {
                **summary.to_payload(),
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
                    "vector_source_dir": str(bundle.vector_source_dir) if bundle.vector_source_dir else None,
                    "vector_document_json": str(bundle.vector_document_json) if bundle.vector_document_json else None,
                    "vector_chunks_jsonl": str(bundle.vector_chunks_jsonl) if bundle.vector_chunks_jsonl else None,
                    "vector_manifest_json": str(bundle.vector_manifest_json) if bundle.vector_manifest_json else None,
                    "summary_markdown": str(bundle.summary_markdown),
                    "summary_json": str(bundle.summary_json),
                    "metadata_json": str(bundle.metadata_json),
                    "checkpoint_json": str(bundle.checkpoint_json) if bundle.checkpoint_json else None,
                    "calibrated_cn_markdown": str(bundle.calibrated_cn_markdown),
                    "calibrated_en_markdown": str(bundle.calibrated_en_markdown),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    return bundle
