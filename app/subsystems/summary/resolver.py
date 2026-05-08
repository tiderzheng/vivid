from __future__ import annotations

import os

from ...constants import DEFAULT_SILICONFLOW_BASE
from ...models.runtime import RuntimeOptions
from .models import (
    DEFAULT_SUMMARY_SYSTEM_PROMPT,
    DEFAULT_SUMMARY_USER_PROMPT,
    SummaryPromptConfig,
    SummaryProviderItem,
    SummaryProviderConfig,
)
from .store import load_summary_provider_store, load_summary_store

DEFAULT_CALIBRATION_CN_SYSTEM_PROMPT = (
    "You are a transcript editor. Take a raw video transcript and produce a "
    "polished, well-formatted Chinese article.\n\n"
    "- Clean up speech artifacts (stuttering, filler words, repetitions)\n"
    "- Add proper punctuation throughout\n"
    "- Organize into logical paragraphs with blank lines between them\n"
    "- Preserve all substantive content, facts, and opinions — do not summarize or omit details\n"
    "- Make it read naturally as a well-written article\n\n"
    "Output only the polished Chinese article. Do NOT use Markdown code blocks. Do NOT add any commentary."
)

DEFAULT_CALIBRATION_CN_USER_PROMPT = (
    "请根据下面的原始逐字稿，生成中文校准版：\n\n"
    "清理所有口语化表达、补全标点符号、组织合理的段落分隔，"
    "形成一篇流畅易读的文章。保留全部实质内容，不要做摘要或删减。\n\n"
    "只输出校准后的文章内容，不要加任何说明。\n\n"
    "Transcript:\n{transcript}"
)

DEFAULT_CALIBRATION_EN_SYSTEM_PROMPT = (
    "You are a translator and editor. Take a Chinese video transcript and produce "
    "a polished, well-formatted English article.\n\n"
    "- Translate the content into natural, fluent English prose\n"
    "- Clean up any speech artifacts\n"
    "- Use proper punctuation and logical paragraph breaks\n"
    "- Preserve all substantive content, facts, and opinions — do not summarize or omit details\n\n"
    "Output only the polished English article. Do NOT use Markdown code blocks. Do NOT add any commentary."
)

DEFAULT_CALIBRATION_EN_USER_PROMPT = (
    "Please translate and polish the following Chinese transcript into a natural, "
    "fluent English article.\n\n"
    "Apply proper punctuation, paragraph breaks, and remove speech artifacts. "
    "Preserve all substantive content — do not summarize or omit details.\n\n"
    "Output only the polished English article, nothing else.\n\n"
    "Transcript:\n{transcript}"
)


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
    store_providers = store.get_providers()
    disabled_provider_ids = {item.id for item in store.providers if not item.enabled}
    resolved: list[SummaryProviderConfig] = []
    for item in store_providers:
        provider = _build_store_provider_config(item, options)
        if provider:
            resolved.append(provider)
    if resolved:
        if (
            options.dashscope_api_key
            and options.dashscope_model
            and not any(item.provider_id == "dashscope" for item in resolved)
        ):
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
    return _build_legacy_summary_provider_configs(options, disabled_provider_ids=disabled_provider_ids)


def _build_store_provider_config(
    item: SummaryProviderItem,
    options: RuntimeOptions,
) -> SummaryProviderConfig | None:
    api_key = _provider_api_key(item, options)
    if not api_key:
        return None
    base_url = item.base_url
    model = item.model
    if item.id == "siliconflow":
        model = options.siliconflow_model or item.model
        if options.siliconflow_base_url != DEFAULT_SILICONFLOW_BASE:
            base_url = options.siliconflow_base_url
    elif item.id == "dashscope":
        model = options.dashscope_model or item.model
    if not model:
        return None
    return SummaryProviderConfig(
        provider_id=item.id,
        provider_name=item.name,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )


def _provider_api_key(item: SummaryProviderItem, options: RuntimeOptions) -> str | None:
    if item.id == "siliconflow":
        return options.siliconflow_api_key or _env_text(item.api_key_env)
    if item.id == "dashscope":
        return options.dashscope_api_key or _env_text(item.api_key_env)
    return _env_text(item.api_key_env)


def _env_text(name: str) -> str | None:
    return (os.environ.get(name) or "").strip() or None


def build_calibration_prompt_configs(options: RuntimeOptions) -> tuple[SummaryPromptConfig, SummaryPromptConfig]:
    store = load_summary_store(options.calibration_prompts_path)
    cn_prompt = store.get_prompt("cn")
    en_prompt = store.get_prompt("en")
    return (
        SummaryPromptConfig(
            prompt_id="cn",
            system_prompt=(
                options.calibration_system_prompt
                or (cn_prompt.system_prompt if cn_prompt else None)
                or DEFAULT_CALIBRATION_CN_SYSTEM_PROMPT
            ),
            user_prompt_template=(
                options.calibration_user_prompt
                or (cn_prompt.user_prompt_template if cn_prompt else None)
                or DEFAULT_CALIBRATION_CN_USER_PROMPT
            ),
        ),
        SummaryPromptConfig(
            prompt_id="en",
            system_prompt=(
                options.calibration_system_prompt
                or (en_prompt.system_prompt if en_prompt else None)
                or DEFAULT_CALIBRATION_EN_SYSTEM_PROMPT
            ),
            user_prompt_template=(
                options.calibration_user_prompt
                or (en_prompt.user_prompt_template if en_prompt else None)
                or DEFAULT_CALIBRATION_EN_USER_PROMPT
            ),
        ),
    )


def _build_legacy_summary_provider_configs(
    options: RuntimeOptions,
    *,
    disabled_provider_ids: set[str] | None = None,
) -> list[SummaryProviderConfig]:
    disabled_provider_ids = disabled_provider_ids or set()
    resolved: list[SummaryProviderConfig] = []
    if (
        "siliconflow" not in disabled_provider_ids
        and options.siliconflow_api_key
        and options.siliconflow_model
    ):
        resolved.append(
            SummaryProviderConfig(
                provider_id="siliconflow",
                provider_name="SiliconFlow",
                base_url=options.siliconflow_base_url,
                model=options.siliconflow_model,
                api_key=options.siliconflow_api_key,
            )
        )
    if "dashscope" not in disabled_provider_ids and options.dashscope_api_key and options.dashscope_model:
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
