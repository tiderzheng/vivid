from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import SummaryPromptItem, SummaryProviderItem


@dataclass(slots=True)
class SummaryPromptStore:
    prompts: list[SummaryPromptItem] = field(default_factory=list)
    selected_prompt_id: str | None = None

    def get_prompt(self, prompt_id: str | None) -> SummaryPromptItem | None:
        resolved_id = prompt_id or self.selected_prompt_id
        if resolved_id:
            for item in self.prompts:
                if item.id == resolved_id:
                    return item
        return self.prompts[0] if self.prompts else None

    def to_payload(self) -> dict:
        return {
            "selected_id": self.selected_prompt_id,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "system_prompt": item.system_prompt,
                    "user_prompt_template": item.user_prompt_template,
                }
                for item in self.prompts
            ],
        }


@dataclass(slots=True)
class SummaryProviderStore:
    providers: list[SummaryProviderItem] = field(default_factory=list)
    selected_provider_id: str | None = None

    def get_providers(self) -> list[SummaryProviderItem]:
        ordered = list(self.providers)
        if self.selected_provider_id:
            for index, item in enumerate(ordered):
                if item.id == self.selected_provider_id:
                    selected = ordered.pop(index)
                    ordered.insert(0, selected)
                    break
        return [item for item in ordered if item.enabled]

    def to_payload(self) -> dict:
        return {
            "selected_id": self.selected_provider_id,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "base_url": item.base_url,
                    "model": item.model,
                    "api_key_env": item.api_key_env,
                    "enabled": item.enabled,
                }
                for item in self.providers
            ],
        }


def load_summary_store(path: Path | None) -> SummaryPromptStore:
    store = SummaryPromptStore()
    if path is None or not path.exists():
        return store
    payload = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    if isinstance(payload, dict):
        store.selected_prompt_id = _text_or_none(payload.get("selected_id"))
        raw_items = payload.get("items", [])
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]
    elif isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
    for item in items:
        prompt_id = _text_or_none(item.get("id"))
        name = _text_or_none(item.get("name"))
        if not prompt_id or not name:
            continue
        store.prompts.append(
            SummaryPromptItem(
                id=prompt_id,
                name=name,
                system_prompt=_text_or_none(item.get("system_prompt")) or "",
                user_prompt_template=_text_or_none(item.get("user_prompt_template")) or "",
            )
        )
    return store


def load_summary_provider_store(path: Path | None) -> SummaryProviderStore:
    store = SummaryProviderStore()
    if path is None or not path.exists():
        return store
    payload = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    if isinstance(payload, dict):
        store.selected_provider_id = _text_or_none(payload.get("selected_id"))
        raw_items = payload.get("items", [])
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]
    elif isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
    for item in items:
        provider_id = _text_or_none(item.get("id"))
        name = _text_or_none(item.get("name"))
        base_url = _text_or_none(item.get("base_url"))
        model = _text_or_none(item.get("model"))
        api_key_env = _text_or_none(item.get("api_key_env"))
        if not provider_id or not name or not base_url or not model or not api_key_env:
            continue
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            enabled = str(enabled).strip().lower() in {"1", "true", "yes", "on"}
        store.providers.append(
            SummaryProviderItem(
                id=provider_id,
                name=name,
                base_url=base_url,
                model=model,
                api_key_env=api_key_env,
                enabled=enabled,
            )
        )
    return store


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
