from __future__ import annotations

import os

from .models import VisionRequestConfig
from .store import load_vision_store
from ...models.runtime import RuntimeOptions


def build_vision_request_config(options: RuntimeOptions) -> VisionRequestConfig:
    store = load_vision_store(options.vision_api_configs_path, options.vision_prompts_path)
    selected_config = store.get_api_config(options.vision_api_config_id)
    selected_prompt = store.get_prompt(options.vision_prompt_id)

    api_key = options.vision_api_key
    if not api_key and selected_config and selected_config.api_key_env:
        api_key = os.environ.get(selected_config.api_key_env) or None

    return VisionRequestConfig(
        api_config_id=options.vision_api_config_id or (selected_config.id if selected_config else None),
        api_base=options.vision_api_base or (selected_config.api_base if selected_config else None),
        api_path=options.vision_api_path or (selected_config.api_path if selected_config else None),
        api_key=api_key,
        model=options.vision_model or (selected_config.model if selected_config else None),
        timeout=options.vision_timeout or (selected_config.timeout if selected_config else None),
        prompt=options.vision_prompt or (selected_prompt.content if selected_prompt else None) or (selected_config.prompt if selected_config else None),
        system_prompt=options.vision_system_prompt or (selected_config.system_prompt if selected_config else None),
        sample_ms=options.vision_sample_ms,
        min_duration_ms=options.vision_min_duration_ms,
    )
