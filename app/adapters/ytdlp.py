from __future__ import annotations

import time
from pathlib import Path

from ..constants import MEDIA_EXTS
from ..exceptions import VividError
from ..services.media_store import newest_file, read_text_file
from ..utils.text import clean_transcript

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
except Exception:  # noqa: BLE001
    YoutubeDL = None
    DownloadError = Exception


class YtDlpAdapter:
    def download_media(
        self,
        source: str,
        workdir: Path,
        *,
        subdir: str = "generic",
        extra_args: list[str] | None = None,
    ) -> Path:
        self._ensure_available()
        outdir = workdir / "media" / subdir
        outdir.mkdir(parents=True, exist_ok=True)
        template = str(outdir / "%(title)s.%(ext)s")
        options = {
            "format": "best",
            "outtmpl": template,
            "noplaylist": True,
            "retries": 2,
            "quiet": True,
            "no_warnings": True,
        }
        self._download(source, options, extra_args)
        media_path = newest_file(outdir, MEDIA_EXTS)
        if not media_path:
            raise VividError("yt-dlp completed but no media file was found.")
        return media_path

    def export_subtitles(
        self,
        source: str,
        workdir: Path,
        *,
        subdir: str = "generic",
        extra_args: list[str] | None = None,
    ) -> str | None:
        self._ensure_available()
        outdir = workdir / "artifacts" / f"{subdir}-subtitle"
        outdir.mkdir(parents=True, exist_ok=True)
        template = str(outdir / "%(title)s.%(ext)s")
        options = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["all"],
            "subtitlesformat": "srt",
            "convertsubtitles": "srt",
            "outtmpl": template,
            "noplaylist": True,
            "retries": 2,
            "quiet": True,
            "no_warnings": True,
        }
        self._download(source, options, extra_args)
        subtitle_path = newest_file(outdir, {".srt", ".vtt", ".lrc", ".txt"})
        if not subtitle_path:
            return None
        text = clean_transcript(read_text_file(subtitle_path))
        return text or None

    def _download(
        self,
        source: str,
        options: dict,
        extra_args: list[str] | None,
    ) -> None:
        merged_options = dict(options)
        merged_options.update(_extra_args_to_options(extra_args))
        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                with YoutubeDL(merged_options) as downloader:
                    downloader.download([source])
                return
            except DownloadError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2)
        raise VividError(f"yt_dlp failed: {last_error}")

    def _ensure_available(self) -> None:
        if YoutubeDL is None:
            raise VividError("Missing Python dependency: yt_dlp. Install with `pip install yt-dlp`.")


def _extra_args_to_options(extra_args: list[str] | None) -> dict:
    if not extra_args:
        return {}
    options: dict[str, str | dict[str, str]] = {}
    headers: dict[str, str] = {}
    index = 0
    while index < len(extra_args):
        item = extra_args[index]
        if item == "--add-header" and index + 1 < len(extra_args):
            raw = extra_args[index + 1]
            if ":" in raw:
                key, value = raw.split(":", 1)
                headers[key.strip()] = value.strip()
            index += 2
            continue
        index += 1
    if headers:
        options["http_headers"] = headers
    return options
