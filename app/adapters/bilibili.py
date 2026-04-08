from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from ..exceptions import VividError
from ..services.media_store import newest_file
from ..utils.subprocess_utils import command_env, run_command


class BilibiliAdapter:
    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = script_path

    def get_video_title(self, source: str) -> str | None:
        """获取Bilibili视频标题，用于项目命名"""
        try:
            script_path = _resolve_script_path(self.script_path)
            command = [
                sys.executable,
                str(script_path),
                "probe",
                "--url",
                source,
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=script_path.parent,
                timeout=30,
                env=_helper_env(),
            )
            if result.returncode == 0:
                # 尝试解析JSON输出
                try:
                    data = json.loads(result.stdout)
                    title = _extract_title_from_probe_payload(data)
                    if title:
                        return title
                except json.JSONDecodeError:
                    pass
            return None
        except Exception:
            return None

    def download_media(
        self,
        source: str,
        workdir: Path,
        ffmpeg_bin: str,
    ) -> Path:
        script_path = _resolve_script_path(self.script_path)
        if shutil.which(ffmpeg_bin) is None and not Path(ffmpeg_bin).expanduser().exists():
            raise VividError(f"ffmpeg not found for Bilibili downloader: {ffmpeg_bin}")
        outdir = workdir / "media" / "bilibili"
        outdir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(script_path),
            "download",
            "--url",
            source,
            "--output",
            str(outdir),
            "--content",
            "video_audio",
            "--episode",
            "current",
            "--ffmpeg",
            ffmpeg_bin,
        ]
        run_command(command, cwd=script_path.parent, retries=2, env=_helper_env())
        media_path = newest_file(outdir, {".mp4", ".mp3", ".m4a", ".flac", ".wav"})
        if not media_path:
            raise VividError("Bilibili helper completed but no media file was produced.")
        return media_path


def _resolve_script_path(script_path: Path | None) -> Path:
    candidate = (script_path or _default_script_path()).expanduser().resolve()
    if not candidate.exists():
        raise VividError(f"Bilibili helper script not found: {candidate}")
    return candidate


def _default_script_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "tools" / "bilibili" / "bili23_agent_cli.py"


def _helper_env() -> dict[str, str]:
    env = command_env()
    env.pop("BILI_SESSDATA", None)
    return env


def _extract_title_from_probe_payload(data: dict) -> str | None:
    detail = data.get("detail", {})
    if isinstance(detail, dict):
        title = str(detail.get("title") or "").strip()
        if title:
            return title

    eps = data.get("eps", [])
    if isinstance(eps, list) and eps:
        first = eps[0] if isinstance(eps[0], dict) else {}
        title = str(first.get("full") or first.get("title") or "").strip()
        if title:
            return title

    episodes = data.get("episodes", [])
    if isinstance(episodes, list) and episodes:
        default_index = data.get("default_episode", 1)
        try:
            index = max(int(default_index) - 1, 0)
        except (TypeError, ValueError):
            index = 0
        if index >= len(episodes):
            index = 0
        episode = episodes[index] if isinstance(episodes[index], dict) else {}
        title = str(episode.get("full") or episode.get("title") or "").strip()
        if title:
            return title
    return None
