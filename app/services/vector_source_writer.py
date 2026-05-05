from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models.calibration import CalibrationResult
from ..models.summary import SummaryResult
from ..models.transcript import TranscriptResult
from ..models.source import SourceInfo


def write_vector_source_bundle(
    workdir: Path,
    source: SourceInfo,
    transcript: TranscriptResult,
    summary: SummaryResult,
    artifacts_dir: Path,
    calibration: CalibrationResult | None = None,
) -> dict[str, Path]:
    vector_dir = workdir / "vector_source"
    vector_dir.mkdir(parents=True, exist_ok=True)
    document_path = vector_dir / "document.json"
    chunks_path = vector_dir / "chunks.jsonl"
    manifest_path = vector_dir / "manifest.json"
    generated_at = datetime.now(timezone.utc).isoformat()

    document = {
        "schema_version": "1",
        "generated_at_utc": generated_at,
        "source": source.raw_source,
        "platform": source.platform,
        "title": source.title,
        "acquisition_method": transcript.acquisition_method,
        "workdir": str(workdir),
        "artifacts_dir": str(artifacts_dir),
        "summary": summary.to_payload(),
        "transcript": {
            "text": transcript.text,
            "media_path": str(transcript.media_path) if transcript.media_path else None,
            "audio_path": str(transcript.audio_path) if transcript.audio_path else None,
        },
        "calibration": calibration.to_payload() if calibration else None,
    }
    document_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    chunks = _build_chunks(document, source, transcript, summary, calibration=calibration)
    chunks_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in chunks),
        encoding="utf-8",
    )

    section_counts = Counter(item["section"] for item in chunks)
    manifest = {
        "schema_version": "1",
        "generated_at_utc": generated_at,
        "workdir": str(workdir),
        "files": {
            "document_json": str(document_path),
            "chunks_jsonl": str(chunks_path),
            "manifest_json": str(manifest_path),
        },
        "chunk_count": len(chunks),
        "chunk_sections": dict(section_counts),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "vector_source_dir": vector_dir,
        "vector_document_json": document_path,
        "vector_chunks_jsonl": chunks_path,
        "vector_manifest_json": manifest_path,
    }


def _build_chunks(
    document: dict[str, Any],
    source: SourceInfo,
    transcript: TranscriptResult,
    summary: SummaryResult,
    calibration: CalibrationResult | None = None,
) -> list[dict[str, Any]]:
    base_meta = {
        "source": source.raw_source,
        "platform": source.platform,
        "title": source.title,
        "acquisition_method": transcript.acquisition_method,
    }
    rows: list[dict[str, Any]] = []
    order = 0

    def append_chunk(section: str, text: str, source_type: str, extra_meta: dict[str, Any] | None = None) -> None:
        nonlocal order
        clean = str(text).strip()
        if not clean:
            return
        order += 1
        rows.append(
            {
                "chunk_id": f"{source_type}-{section}-{order}",
                "section": section,
                "text": clean,
                "source_type": source_type,
                "order": order,
                "metadata": {
                    **base_meta,
                    **(extra_meta or {}),
                },
            }
        )

    append_chunk("title", summary.title, "summary")
    append_chunk("overview", summary.overview, "summary")
    append_chunk("core_points", "\n".join(summary.core_points), "summary", {"item_count": len(summary.core_points)})
    append_chunk("controversies", "\n".join(summary.controversies), "summary", {"item_count": len(summary.controversies)})
    append_chunk(
        "action_suggestions",
        "\n".join(summary.action_suggestions),
        "summary",
        {"item_count": len(summary.action_suggestions)},
    )
    append_chunk("playful_comment", summary.playful_comment, "summary")

    transcript_parts = [part.strip() for part in transcript.text.split("\n\n") if part.strip()]
    if not transcript_parts and transcript.text.strip():
        transcript_parts = [transcript.text.strip()]
    for index, part in enumerate(transcript_parts, start=1):
        append_chunk("transcript", part, "transcript", {"part_index": index})
    if calibration is not None:
        append_chunk("calibrated_cn", calibration.cn_text, "calibration", {"language": "zh"})
        append_chunk("calibrated_en", calibration.en_text, "calibration", {"language": "en"})
    return rows
