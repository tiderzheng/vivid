from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from pathlib import Path

from ...exceptions import VividError
from ...utils.text import clean_transcript
from .device import resolve_runtime_device
from .ffmpeg_service import ensure_ffmpeg_available, extract_audio, is_audio_file
from .models import TranscriptionRequestConfig
from .whisper_service import WhisperService


@dataclass(slots=True)
class InternalTranscriptionResult:
    transcript: str
    audio_path: Path
    runtime_device: str


class InternalTranscriptionEngine:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", whisper_root: Path | None = None) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.whisper = WhisperService(whisper_root=whisper_root)

    def transcribe(
        self,
        source_path: Path,
        workdir: Path,
        timeout_seconds: int,
        request_config: TranscriptionRequestConfig,
    ) -> InternalTranscriptionResult:
        audio_path = self._prepare_audio(source_path, workdir, request_config)
        runtime_device = resolve_runtime_device(request_config.device)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self.whisper.transcribe,
                audio_path,
                request_config.model,
                runtime_device,
                request_config.language,
                request_config.task,
            )
            try:
                result = future.result(timeout=timeout_seconds)
            except TimeoutError as exc:
                raise VividError(f"Internal transcription timed out after {timeout_seconds}s.") from exc
        transcript = clean_transcript(result.get("text") or "")
        if not transcript:
            raise VividError("Internal transcription completed but returned empty transcript.")
        return InternalTranscriptionResult(
            transcript=transcript,
            audio_path=audio_path,
            runtime_device=runtime_device,
        )

    def _prepare_audio(
        self,
        source_path: Path,
        workdir: Path,
        request_config: TranscriptionRequestConfig,
    ) -> Path:
        if not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        if is_audio_file(source_path) and not request_config.extract_audio:
            return source_path
        ensure_ffmpeg_available(self.ffmpeg_bin)
        audio_path = workdir / "media" / "audio" / f"{source_path.stem}.wav"
        return extract_audio(source_path, audio_path, ffmpeg_bin=self.ffmpeg_bin)
