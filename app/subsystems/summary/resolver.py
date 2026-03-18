from __future__ import annotations

from ...models.runtime import RuntimeOptions
from .models import DEFAULT_SUMMARY_SYSTEM_PROMPT, DEFAULT_SUMMARY_USER_PROMPT, SummaryPromptConfig
from .store import load_summary_store


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
