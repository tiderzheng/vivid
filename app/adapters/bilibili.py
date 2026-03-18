from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from ..exceptions import BilibiliSessdataExpiredError, VividError
from ..services.media_store import newest_file, read_text_file
from ..utils.subprocess_utils import run_command
from ..utils.text import clean_transcript

_SESSDATA_EXPIRED_MARKERS = (
    "api error -101",
    "账号未登录",
    "登录失效",
    "请先登录",
    "not logged in",
    "login required",
)


class BilibiliAdapter:
    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = script_path

    def get_video_title(self, source: str, sessdata: str | None) -> str | None:
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
            if sessdata:
                command.extend(["--sessdata", sessdata])
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=script_path.parent,
                timeout=30
            )
            _raise_if_sessdata_expired_message(
                f"{result.stdout or ''}\n{result.stderr or ''}",
                sessdata,
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
        except BilibiliSessdataExpiredError:
            raise
        except Exception:
            return None

    def export_subtitles(self, source: str, workdir: Path, sessdata: str | None) -> str | None:
        script_path = _resolve_script_path(self.script_path)
        outdir = workdir / "artifacts" / "bilibili-subtitle"
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
            "none",
            "--episode",
            "current",
            "--subtitle-format",
            "srt",
            "--subtitle-lang",
            "all",
        ]
        if sessdata:
            command.extend(["--sessdata", sessdata])
        try:
            run_command(command, cwd=script_path.parent, retries=2)
        except VividError as exc:
            _raise_if_sessdata_expired(exc, sessdata)
            raise
        subtitle_path = newest_file(outdir, {".srt", ".txt", ".lrc"})
        if not subtitle_path:
            return None
        text = clean_transcript(read_text_file(subtitle_path))
        return text or None

    def download_media(
        self,
        source: str,
        workdir: Path,
        sessdata: str | None,
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
        if sessdata:
            command.extend(["--sessdata", sessdata])
        try:
            run_command(command, cwd=script_path.parent, retries=2)
        except VividError as exc:
            _raise_if_sessdata_expired(exc, sessdata)
            raise
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


def _raise_if_sessdata_expired(exc: VividError, sessdata: str | None) -> None:
    if not sessdata:
        return
    _raise_if_sessdata_expired_message(str(exc), sessdata, exc)


def _raise_if_sessdata_expired_message(
    detail: str,
    sessdata: str | None,
    source_exc: Exception | None = None,
) -> None:
    if not sessdata:
        return
    lowered = detail.lower()
    if any(marker.lower() in lowered for marker in _SESSDATA_EXPIRED_MARKERS):
        raise BilibiliSessdataExpiredError(detail) from source_exc


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
