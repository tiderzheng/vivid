from __future__ import annotations

import shutil
from pathlib import Path

from ..constants import MEDIA_EXTS, VIDEO_EXTS


def media_dir(workdir: Path) -> Path:
    path = workdir / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def newest_file(root: Path, allowed_exts: set[str]) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in allowed_exts]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def copy_into_dir(source_path: Path | None, target_dir: Path) -> Path | None:
    if not source_path or not source_path.exists():
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / source_path.name
    if source_path.resolve() == destination.resolve():
        return destination
    shutil.copy2(source_path, destination)
    return destination


def is_media_file(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTS


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS
