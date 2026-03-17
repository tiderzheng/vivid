from __future__ import annotations

import shutil
import sys
from pathlib import Path

from ..exceptions import VividError
from ..services.media_store import newest_file, read_text_file
from ..utils.subprocess_utils import run_command
from ..utils.text import clean_transcript


class BilibiliAdapter:
    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = script_path

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
        run_command(command, cwd=script_path.parent, retries=2)
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
        run_command(command, cwd=script_path.parent, retries=2)
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
