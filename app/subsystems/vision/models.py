from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class VisionApiConfig:
    id: str
    name: str
    api_base: str
    api_path: str = "/v1/chat/completions"
    model: str = ""
    timeout: int = 30
    group: str = "default"
    note: str = ""
    prompt: str = ""
    system_prompt: str = ""
    api_key_env: str | None = None


@dataclass(slots=True)
class VisionPromptItem:
    id: str
    name: str
    content: str


@dataclass(slots=True)
class VisionRequestConfig:
    api_config_id: str | None = None
    api_base: str | None = None
    api_path: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout: int | None = None
    prompt: str | None = None
    system_prompt: str | None = None
    sample_ms: int = 800
    min_duration_ms: int = 1200

    def to_eyes_payload(self, video_path: Path, output_path: Path) -> dict:
        payload = {
            "video_path": str(video_path),
            "sample_ms": self.sample_ms,
            "min_duration_ms": self.min_duration_ms,
            "output_path": str(output_path),
        }
        if self.api_config_id:
            payload["api_config_id"] = self.api_config_id
        if self.api_base:
            payload["api_base"] = self.api_base
        if self.api_path:
            payload["api_path"] = self.api_path
        if self.api_key:
            payload["api_key"] = self.api_key
        if self.model:
            payload["model"] = self.model
        if self.timeout:
            payload["timeout"] = self.timeout
        if self.prompt:
            payload["prompt"] = self.prompt
        if self.system_prompt:
            payload["system_prompt"] = self.system_prompt
        return payload
