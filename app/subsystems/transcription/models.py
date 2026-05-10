from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class TranscriptionPreset:
    id: str
    name: str
    model: str = "large-v3-turbo"
    device: str = "auto"
    language: str | None = "zh"
    task: str = "transcribe"
    extract_audio: bool = True
    note: str = ""


@dataclass(slots=True)
class TranscriptionRequestConfig:
    model: str = "large-v3-turbo"
    device: str = "auto"
    language: str | None = "zh"
    task: str = "transcribe"
    extract_audio: bool = True
    output_dir: Path | None = None

    def to_ears4_payload(self, source_path: Path) -> dict:
        payload = {
            "source_path": str(source_path),
            "model": self.model,
            "device": self.device,
            "language": self.language or None,
            "task": self.task,
            "extract_audio": self.extract_audio,
        }
        if self.output_dir:
            payload["output_dir"] = str(self.output_dir)
        return payload
