from __future__ import annotations

from ..models.transcript import TranscriptResult


def normalize_transcript(result: TranscriptResult) -> TranscriptResult:
    cleaned = result.text.strip()
    return TranscriptResult(
        text=cleaned,
        acquisition_method=result.acquisition_method,
        media_path=result.media_path,
        audio_path=result.audio_path,
    )
