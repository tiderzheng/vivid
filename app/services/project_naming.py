from __future__ import annotations

import re
from pathlib import Path


def sanitize_name(value: str, fallback: str = "video") -> str:
    cleaned = re.sub(r"[<>:\"/\\\\|?*]+", "_", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:120] or fallback


def derive_title(source: str, project_name: str | None = None) -> str:
    if project_name:
        return sanitize_name(project_name)
    return sanitize_name(source_stem(source))


def source_stem(source: str) -> str:
    source_path = Path(source)
    if source_path.exists():
        return source_path.stem
    path_part = re.sub(r"^https?://", "", source).split("?", 1)[0].rstrip("/")
    if "/" in path_part:
        path_part = path_part.rsplit("/", 1)[-1]
    return Path(path_part).stem or "video"


def infer_video_title(source: str, media_path: Path | None, workdir: Path) -> str:
    if media_path:
        return sanitize_name(media_path.stem)
    artifacts_dir = workdir / "artifacts"
    if artifacts_dir.exists():
        for candidate in sorted(artifacts_dir.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in {".srt", ".txt", ".lrc", ".json"}:
                stem = re.sub(r"_(zh|en|jp|ja|unknown)$", "", candidate.stem, flags=re.I)
                return sanitize_name(stem)
    return sanitize_name(source_stem(source))
