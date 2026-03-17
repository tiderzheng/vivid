from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class TranscriptResult:
    text: str
    acquisition_method: str
    media_path: Path | None = None
    audio_path: Path | None = None
