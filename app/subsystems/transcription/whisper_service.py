from __future__ import annotations

import contextlib
import io
import threading
from pathlib import Path
from typing import Any


class WhisperService:
    def __init__(self, whisper_root: Path | None = None) -> None:
        self._whisper_root = whisper_root
        self._model_class: Any | None = None
        self._models: dict[tuple[str, str, str], Any] = {}
        self._lock = threading.Lock()

    def _ensure_model_class(self) -> Any:
        if self._model_class is not None:
            return self._model_class

        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Cannot import faster_whisper module. Install faster-whisper from requirements.txt."
            ) from exc

        self._model_class = WhisperModel
        return WhisperModel

    def _get_model(self, model_name: str, device: str) -> Any:
        compute_type = _compute_type_for_device(device)
        key = (model_name, device, compute_type)
        if key in self._models:
            return self._models[key]

        with self._lock:
            if key in self._models:
                return self._models[key]
            whisper_model = self._ensure_model_class()
            kwargs: dict[str, Any] = {
                "device": device,
                "compute_type": compute_type,
            }
            if self._whisper_root:
                self._whisper_root.mkdir(parents=True, exist_ok=True)
                kwargs["download_root"] = str(self._whisper_root)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                model = whisper_model(model_name, **kwargs)
            self._models[key] = model
            return model

    def transcribe(
        self,
        audio_path: Path,
        model_name: str,
        device: str,
        language: str | None,
        task: str,
    ) -> dict[str, Any]:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._get_model(model_name=model_name, device=device)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            segments, info = model.transcribe(
                str(audio_path),
                language=language or None,
                task=task,
            )
            segment_payloads = [_segment_to_payload(segment, index) for index, segment in enumerate(segments)]
        return {
            "text": "".join(str(item.get("text") or "") for item in segment_payloads).strip(),
            "segments": segment_payloads,
            "language": getattr(info, "language", None),
        }


def _compute_type_for_device(device: str) -> str:
    return "float16" if device == "cuda" else "int8"


def _segment_to_payload(segment: Any, fallback_id: int) -> dict[str, Any]:
    if isinstance(segment, dict):
        return {
            "id": segment.get("id", fallback_id),
            "start": segment.get("start"),
            "end": segment.get("end"),
            "text": segment.get("text") or "",
        }
    return {
        "id": getattr(segment, "id", fallback_id),
        "start": getattr(segment, "start", None),
        "end": getattr(segment, "end", None),
        "text": getattr(segment, "text", "") or "",
    }
