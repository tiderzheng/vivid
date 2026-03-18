from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SUMMARY_SYSTEM_PROMPT = (
    "You summarize video transcripts. Return valid JSON only with keys "
    '"one_line", "detailed_summary", and "key_points". '
    "key_points must be an array of 3 to 5 concise strings."
)

DEFAULT_SUMMARY_USER_PROMPT = (
    "Summarize the transcript below in Chinese.\n"
    "Requirements:\n"
    "1. one_line: one sentence.\n"
    "2. detailed_summary: one compact paragraph.\n"
    "3. key_points: 3-5 bullets.\n"
    "4. Do not include markdown fences.\n\n"
    "Transcript:\n{transcript}"
)


@dataclass(slots=True)
class SummaryPromptItem:
    id: str
    name: str
    system_prompt: str = ""
    user_prompt_template: str = ""


@dataclass(slots=True)
class SummaryPromptConfig:
    prompt_id: str | None = None
    system_prompt: str = DEFAULT_SUMMARY_SYSTEM_PROMPT
    user_prompt_template: str = DEFAULT_SUMMARY_USER_PROMPT
