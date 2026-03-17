from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import TranscriptionPreset


@dataclass(slots=True)
class TranscriptionConfigStore:
    presets: list[TranscriptionPreset] = field(default_factory=list)
    selected_preset_id: str | None = None

    def get_preset(self, preset_id: str | None) -> TranscriptionPreset | None:
        if preset_id:
            for item in self.presets:
                if item.id == preset_id:
                    return item
            return None
        if self.selected_preset_id:
            for item in self.presets:
                if item.id == self.selected_preset_id:
                    return item
        return self.presets[0] if self.presets else None

    def upsert_preset(self, preset: TranscriptionPreset) -> None:
        for index, item in enumerate(self.presets):
            if item.id == preset.id:
                self.presets[index] = preset
                return
        self.presets.append(preset)

    def select_preset(self, preset_id: str) -> bool:
        if self.get_preset(preset_id) is None:
            return False
        self.selected_preset_id = preset_id
        return True

    def to_payload(self) -> dict:
        return {
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "model": item.model,
                    "device": item.device,
                    "language": item.language,
                    "task": item.task,
                    "extract_audio": item.extract_audio,
                    "note": item.note,
                }
                for item in self.presets
            ],
            "selected_id": self.selected_preset_id,
        }


def load_transcription_store(presets_path: Path) -> TranscriptionConfigStore:
    store = TranscriptionConfigStore()
    if not presets_path.exists():
        return store
    payload = json.loads(presets_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        store.selected_preset_id = payload.get("selected_id")
        for item in payload.get("items", []):
            store.presets.append(
                TranscriptionPreset(
                    id=str(item.get("id", "")).strip(),
                    name=str(item.get("name", "")).strip(),
                    model=str(item.get("model", "base")).strip() or "base",
                    device=str(item.get("device", "auto")).strip() or "auto",
                    language=(str(item.get("language", "")).strip() or None),
                    task=str(item.get("task", "transcribe")).strip() or "transcribe",
                    extract_audio=bool(item.get("extract_audio", True)),
                    note=str(item.get("note", "")).strip(),
                )
            )
    return store


def save_transcription_store(store: TranscriptionConfigStore, presets_path: Path) -> None:
    presets_path.parent.mkdir(parents=True, exist_ok=True)
    presets_path.write_text(
        json.dumps(store.to_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
