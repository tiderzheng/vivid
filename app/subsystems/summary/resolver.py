from __future__ import annotations

import os

from ...models.runtime import RuntimeOptions
from .models import (
    DEFAULT_SUMMARY_SYSTEM_PROMPT,
    DEFAULT_SUMMARY_USER_PROMPT,
    SummaryPromptConfig,
    SummaryProviderConfig,
)
from .store import load_summary_provider_store, load_summary_store


def build_summary_prompt_config(options: RuntimeOptions) -> SummaryPromptConfig:
    store = load_summary_store(options.summary_prompts_path)
    selected_prompt = store.get_prompt(options.summary_prompt_id)
    return SummaryPromptConfig(
        prompt_id=options.summary_prompt_id or (selected_prompt.id if selected_prompt else None),
        system_prompt=(
            options.summary_system_prompt
            or (selected_prompt.system_prompt if selected_prompt else None)
            or DEFAULT_SUMMARY_SYSTEM_PROMPT
        ),
        user_prompt_template=(
            options.summary_user_prompt
            or (selected_prompt.user_prompt_template if selected_prompt else None)
            or DEFAULT_SUMMARY_USER_PROMPT
        ),
    )


def build_summary_provider_configs(options: RuntimeOptions) -> list[SummaryProviderConfig]:
    store = load_summary_provider_store(options.summary_providers_path)
    resolved: list[SummaryProviderConfig] = []
    for item in store.get_providers():
        api_key = (os.environ.get(item.api_key_env) or "").strip()
        if not api_key:
            continue
        model = item.model
        if item.id == "siliconflow":
            model = options.siliconflow_model or model
        elif item.id == "dashscope":
            model = options.dashscope_model or model
        resolved.append(
            SummaryProviderConfig(
                provider_id=item.id,
                provider_name=item.name,
                base_url=item.base_url,
                model=model,
                api_key=api_key,
            )
        )
    if resolved:
        return resolved
    return _build_legacy_summary_provider_configs(options)


def _build_legacy_summary_provider_configs(options: RuntimeOptions) -> list[SummaryProviderConfig]:
    resolved: list[SummaryProviderConfig] = []
    if options.siliconflow_api_key:
        resolved.append(
            SummaryProviderConfig(
                provider_id="siliconflow",
                provider_name="SiliconFlow",
                base_url=options.siliconflow_base_url,
                model=options.siliconflow_model,
                api_key=options.siliconflow_api_key,
            )
        )
    if options.dashscope_api_key:
        resolved.append(
            SummaryProviderConfig(
                provider_id="dashscope",
                provider_name="DashScope",
                base_url=options.dashscope_base_url,
                model=options.dashscope_model,
                api_key=options.dashscope_api_key,
            )
        )
    return resolved
