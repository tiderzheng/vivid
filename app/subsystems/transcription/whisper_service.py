from __future__ import annotations

import contextlib
import io
import sys
import threading
from pathlib import Path
from typing import Any


class WhisperService:
    def __init__(self, whisper_root: Path | None = None) -> None:
        self._whisper_root = whisper_root
        self._module: Any | None = None
        self._models: dict[tuple[str, str], Any] = {}
        self._lock = threading.Lock()

    def _ensure_module(self) -> Any:
        if self._module is not None:
            return self._module

        if self._whisper_root:
            whisper_root_str = str(self._whisper_root)
            if whisper_root_str not in sys.path:
                sys.path.insert(0, whisper_root_str)

        try:
            import whisper  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Cannot import whisper module. Install openai-whisper or set VIVID_WHISPER_ROOT."
            ) from exc

        self._module = whisper
        return whisper

    def _get_model(self, model_name: str, device: str) -> Any:
        key = (model_name, device)
        if key in self._models:
            return self._models[key]

        with self._lock:
            if key in self._models:
                return self._models[key]
            whisper = self._ensure_module()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                model = whisper.load_model(model_name, device=device)
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
            result = model.transcribe(
                str(audio_path),
                language=language or None,
                task=task,
                fp16=(device == "cuda"),
                verbose=False,
            )
        return {
            "text": (result.get("text") or "").strip(),
            "segments": result.get("segments", []),
            "language": result.get("language"),
        }
