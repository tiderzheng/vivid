from __future__ import annotations

import re
from pathlib import Path

from ..constants import VIDEO_EXTS


def trim_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip()


def trim_for_llm(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[TRUNCATED]"


def clean_transcript(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sentence_split(text: str) -> list[str]:
    raw_parts = re.split(r"(?<=[。！？!?\.])\s+|\n+", text)
    return [part.strip() for part in raw_parts if part.strip()]


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS
