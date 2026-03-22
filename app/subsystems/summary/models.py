from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SUMMARY_SYSTEM_PROMPT = (
    "You summarize video transcripts for a Chinese quickread workflow. "
    'Return valid JSON only with keys "title", "overview", "core_points", '
    '"controversies", "action_suggestions", and "playful_comment". '
    "core_points must be an array of 3 to 5 concise strings. "
    "controversies must be an array of 1 to 3 concise strings; if the source has no obvious dispute, "
    "write verification angles instead of returning an empty array. "
    "action_suggestions must be an array of 3 to 5 concise strings focused on further reading, "
    "learning direction, and fact-checking."
)

DEFAULT_SUMMARY_USER_PROMPT = (
    "请根据下面的逐字稿，输出中文总结。\n"
    "要求：\n"
    "1. title：像标题一样的短句，适合直接当内容名。\n"
    "2. overview：一段紧凑的内容概览。\n"
    "3. core_points：3-5 条核心观点。\n"
    "4. controversies：1-3 条争议点；如果没有明显争议，就写出最值得继续核查的角度。\n"
    "5. action_suggestions：3-5 条行动建议，必须包含推荐相关阅读、继续学习方向、以及证真/交叉验证建议。\n"
    "6. playful_comment：1-2 句俏皮点评，轻一点，但不要油腻。\n"
    "7. 不要输出 Markdown 代码块。\n\n"
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
