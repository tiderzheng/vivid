from __future__ import annotations

import subprocess
from pathlib import Path


AUDIO_SUFFIXES = {".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg", ".wma"}


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_SUFFIXES


def ensure_ffmpeg_available(ffmpeg_bin: str) -> None:
    result = subprocess.run(
        [ffmpeg_bin, "-version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("ffmpeg is not available.")


def extract_audio(
    input_path: Path,
    output_path: Path,
    ffmpeg_bin: str,
    sample_rate: int = 16000,
) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip().splitlines()
        error_line = stderr[-1] if stderr else "Unknown ffmpeg error."
        raise RuntimeError(f"ffmpeg extraction failed: {error_line}")
    return output_path
