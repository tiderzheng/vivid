from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import VisionApiConfig, VisionPromptItem


@dataclass(slots=True)
class VisionConfigStore:
    api_configs: list[VisionApiConfig] = field(default_factory=list)
    selected_api_config_id: str | None = None
    prompts: list[VisionPromptItem] = field(default_factory=list)

    def get_api_config(self, config_id: str | None) -> VisionApiConfig | None:
        if config_id:
            for item in self.api_configs:
                if item.id == config_id:
                    return item
            return None
        if self.selected_api_config_id:
            for item in self.api_configs:
                if item.id == self.selected_api_config_id:
                    return item
        return self.api_configs[0] if self.api_configs else None

    def get_prompt(self, prompt_id: str | None) -> VisionPromptItem | None:
        if not prompt_id:
            return None
        for item in self.prompts:
            if item.id == prompt_id:
                return item
        return None

    def upsert_api_config(self, config: VisionApiConfig) -> None:
        for index, item in enumerate(self.api_configs):
            if item.id == config.id:
                self.api_configs[index] = config
                return
        self.api_configs.append(config)

    def upsert_prompt(self, prompt: VisionPromptItem) -> None:
        for index, item in enumerate(self.prompts):
            if item.id == prompt.id:
                self.prompts[index] = prompt
                return
        self.prompts.append(prompt)

    def select_api_config(self, config_id: str) -> bool:
        if self.get_api_config(config_id) is None:
            return False
        self.selected_api_config_id = config_id
        return True

    def to_api_payload(self) -> dict:
        return {
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "api_base": item.api_base,
                    "api_path": item.api_path,
                    "model": item.model,
                    "timeout": item.timeout,
                    "group": item.group,
                    "note": item.note,
                    "prompt": item.prompt,
                    "system_prompt": item.system_prompt,
                    "api_key_env": item.api_key_env,
                }
                for item in self.api_configs
            ],
            "selected_id": self.selected_api_config_id,
        }

    def to_prompt_payload(self) -> list[dict]:
        return [
            {
                "id": item.id,
                "name": item.name,
                "content": item.content,
            }
            for item in self.prompts
        ]


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_vision_store(api_configs_path: Path, prompts_path: Path) -> VisionConfigStore:
    store = VisionConfigStore()
    api_payload = _load_json(api_configs_path)
    if isinstance(api_payload, dict):
        store.selected_api_config_id = api_payload.get("selected_id")
        for item in api_payload.get("items", []):
            store.api_configs.append(
                VisionApiConfig(
                    id=str(item.get("id", "")).strip(),
                    name=str(item.get("name", "")).strip(),
                    api_base=str(item.get("api_base") or item.get("url") or "").strip(),
                    api_path=str(item.get("api_path", "/v1/chat/completions")).strip() or "/v1/chat/completions",
                    model=str(item.get("model", "")).strip(),
                    timeout=int(item.get("timeout", 30) or 30),
                    group=str(item.get("group", "default")).strip() or "default",
                    note=str(item.get("note", "")).strip(),
                    prompt=str(item.get("prompt", "")).strip(),
                    system_prompt=str(item.get("system_prompt", "")).strip(),
                    api_key_env=str(item.get("api_key_env", "")).strip() or None,
                )
            )
    prompt_payload = _load_json(prompts_path)
    if isinstance(prompt_payload, list):
        for item in prompt_payload:
            store.prompts.append(
                VisionPromptItem(
                    id=str(item.get("id", "")).strip(),
                    name=str(item.get("name", "")).strip(),
                    content=str(item.get("content", "")).strip(),
                )
            )
    return store


def save_vision_store(store: VisionConfigStore, api_configs_path: Path, prompts_path: Path) -> None:
    api_configs_path.parent.mkdir(parents=True, exist_ok=True)
    prompts_path.parent.mkdir(parents=True, exist_ok=True)
    api_configs_path.write_text(
        json.dumps(store.to_api_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    prompts_path.write_text(
        json.dumps(store.to_prompt_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
