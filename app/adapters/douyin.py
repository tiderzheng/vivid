from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..constants import MEDIA_EXTS
from ..exceptions import VividError
from ..services.media_store import newest_file
from ..utils.subprocess_utils import run_command

_TITLE_FETCH_TIMEOUT_SECONDS = 8


class DouyinAdapter:
    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = script_path

    def get_video_title(self, source: str) -> str | None:
        """获取抖音视频标题，用于项目命名"""
        script_path = _resolve_script_path(self.script_path)
        if shutil.which("node") is None:
            raise VividError("Missing runtime dependency: node. Douyin title fetch requires Node.js.")
        try:
            result = subprocess.run(
                ["node", str(script_path), "info", source],
                capture_output=True,
                text=True,
                cwd=script_path.parent,
                timeout=_TITLE_FETCH_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise VividError(
                f"Douyin title fetch timed out after {_TITLE_FETCH_TIMEOUT_SECONDS} seconds."
            ) from exc
        except OSError as exc:
            raise VividError(f"Douyin title fetch failed to start: {exc}") from exc

        if result.returncode != 0:
            detail = _probe_error_detail(result.stdout, result.stderr)
            raise VividError(f"Douyin title fetch failed. {detail}")

        return _parse_title_from_output(result.stdout)

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


def _parse_title_from_output(output: str) -> str | None:
    for line in output.splitlines():
        text = line.strip()
        if not text:
            continue
        match = re.search(r"标题[:：]\s*(.+)$", text)
        if match:
            title = match.group(1).strip()
            if title:
                return title
    return None


def _probe_error_detail(stdout: str, stderr: str) -> str:
    for candidate in [stderr.strip(), stdout.strip()]:
        if candidate:
            return candidate.splitlines()[-1].strip()
    return "helper returned a non-zero exit code."
