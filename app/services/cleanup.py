from __future__ import annotations

import shutil
from pathlib import Path


def cleanup_media(workdir: Path) -> None:
    shutil.rmtree(workdir / "media", ignore_errors=True)
