from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ArtifactBundle:
    workdir: Path
    artifacts_dir: Path
    quickread_markdown: Path
    transcript_text: Path
    summary_markdown: Path
    summary_json: Path
    metadata_json: Path
    checkpoint_json: Path | None = None
    vector_source_dir: Path | None = None
    vector_document_json: Path | None = None
    vector_chunks_jsonl: Path | None = None
    vector_manifest_json: Path | None = None
