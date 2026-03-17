from __future__ import annotations

import re
import shutil
import time
import uuid
from pathlib import Path

from .project_naming import sanitize_name, source_stem


def ensure_workdir(data_dir: Path, title: str) -> Path:
    workdir = data_dir.expanduser().resolve() / title
    (workdir / "artifacts").mkdir(parents=True, exist_ok=True)
    (workdir / "media").mkdir(parents=True, exist_ok=True)
    return workdir


def make_staging_workdir(data_root: Path, source: str) -> Path:
    root = data_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    staging_root = root / "_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", source_stem(source)).strip("-").lower() or "video"
    workdir = staging_root / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}-{uuid.uuid4().hex[:8]}"
    (workdir / "artifacts").mkdir(parents=True, exist_ok=True)
    (workdir / "media").mkdir(parents=True, exist_ok=True)
    return workdir


def move_to_final_workdir(staging_dir: Path, data_root: Path, title: str) -> Path:
    final_dir = data_root.expanduser().resolve() / sanitize_name(title)
    if not final_dir.exists():
        shutil.move(str(staging_dir), str(final_dir))
        return final_dir
    suffix = 2
    while True:
        candidate = data_root.expanduser().resolve() / f"{sanitize_name(title)}-{suffix}"
        if not candidate.exists():
            shutil.move(str(staging_dir), str(candidate))
            return candidate
        suffix += 1


def relocate_path(path: Path | None, old_root: Path, new_root: Path) -> Path | None:
    if not path:
        return None
    try:
        relative = path.resolve().relative_to(old_root.resolve())
    except ValueError:
        return path
    return new_root / relative
