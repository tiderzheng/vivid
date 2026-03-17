from __future__ import annotations

import shutil
from pathlib import Path

from ..constants import MEDIA_EXTS
from ..exceptions import VividError
from ..services.media_store import newest_file
from ..utils.subprocess_utils import run_command


class DouyinAdapter:
    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = script_path

    def download_media(self, source: str, workdir: Path) -> Path:
        script_path = _resolve_script_path(self.script_path)
        if shutil.which("node") is None:
            raise VividError("Missing runtime dependency: node. Douyin download requires Node.js.")
        outdir = workdir / "media" / "douyin"
        outdir.mkdir(parents=True, exist_ok=True)
        run_command(
            ["node", str(script_path), "download", source, "-o", str(outdir)],
            cwd=script_path.parent,
            retries=2,
        )
        media_path = newest_file(outdir, MEDIA_EXTS)
        if not media_path:
            raise VividError("Douyin helper completed but no media file was produced.")
        return media_path


def _resolve_script_path(script_path: Path | None) -> Path:
    candidate = (script_path or _default_script_path()).expanduser().resolve()
    if not candidate.exists():
        raise VividError(f"Douyin helper script not found: {candidate}")
    return candidate


def _default_script_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "tools" / "douyin" / "douyin.js"
