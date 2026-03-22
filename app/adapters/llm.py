from __future__ import annotations

import requests

from ..exceptions import VividError
from ..models.summary import SummaryResult
from ..utils.json_utils import extract_json_block
from ..utils.logging_utils import log_event, log_exception
from ..utils.text import sentence_split, trim_for_llm


class LlmAdapter:
    def __init__(
        self,
        *,
        siliconflow_api_key: str | None,
        dashscope_api_key: str | None,
        siliconflow_base_url: str,
        dashscope_base_url: str,
        siliconflow_model: str,
        dashscope_model: str,
        llm_max_chars: int,
        summary_system_prompt: str,
        summary_user_prompt: str,
    ) -> None:
        self.siliconflow_api_key = siliconflow_api_key
        self.dashscope_api_key = dashscope_api_key
        self.siliconflow_base_url = siliconflow_base_url
        self.dashscope_base_url = dashscope_base_url
        self.siliconflow_model = siliconflow_model
        self.dashscope_model = dashscope_model
        self.llm_max_chars = llm_max_chars
        self.summary_system_prompt = summary_system_prompt
        self.summary_user_prompt = summary_user_prompt

    def summarize(self, transcript: str) -> SummaryResult:
        clipped = trim_for_llm(transcript, self.llm_max_chars)
        failures: list[str] = []
        if self.siliconflow_api_key:
            try:
                return self._request_summary(
                    api_key=self.siliconflow_api_key,
                    base_url=self.siliconflow_base_url,
                    model=self.siliconflow_model,
                    transcript=clipped,
                    provider_label=f"SiliconFlow {self.siliconflow_model}",
                )
            except Exception as exc:
                failures.append(f"SiliconFlow {self.siliconflow_model}: {exc}")
                log_exception(
                    "summary_provider_failed",
                    exc,
                    provider="siliconflow",
                    model=self.siliconflow_model,
                    base_url=self.siliconflow_base_url,
                )
        if self.dashscope_api_key:
            try:
                return self._request_summary(
                    api_key=self.dashscope_api_key,
                    base_url=self.dashscope_base_url,
                    model=self.dashscope_model,
                    transcript=clipped,
                    provider_label=f"DashScope {self.dashscope_model}",
                )
            except Exception as exc:
                failures.append(f"DashScope {self.dashscope_model}: {exc}")
                log_exception(
                    "summary_provider_failed",
                    exc,
                    provider="dashscope",
                    model=self.dashscope_model,
                    base_url=self.dashscope_base_url,
                )
        if failures:
            log_event("summary_fallback_used", failures=failures, fallback="rule_based")
        return fallback_summary(transcript)

    def _request_summary(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        transcript: str,
        provider_label: str,
    ) -> SummaryResult:
        system_prompt = self.summary_system_prompt
        user_prompt = self._render_summary_user_prompt(transcript)
        response = requests.post(
            base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = extract_json_block(content)
        title = str(parsed.get("title") or parsed.get("one_line") or "").strip()
        overview = str(parsed.get("overview") or parsed.get("detailed_summary") or parsed.get("detailed") or "").strip()
        core_points = [str(item).strip() for item in parsed.get("core_points", parsed.get("key_points", [])) if str(item).strip()]
        controversies = [str(item).strip() for item in parsed.get("controversies", []) if str(item).strip()]
        action_suggestions = [str(item).strip() for item in parsed.get("action_suggestions", []) if str(item).strip()]
        playful_comment = str(parsed.get("playful_comment") or "").strip()
        if not title:
            raise VividError(f"{provider_label} returned no title.")
        if not overview:
            raise VividError(f"{provider_label} returned no overview.")
        if not core_points:
            raise VividError(f"{provider_label} returned no core points.")
        if not controversies:
            raise VividError(f"{provider_label} returned no controversies.")
        if not action_suggestions:
            raise VividError(f"{provider_label} returned no action suggestions.")
        if not playful_comment:
            raise VividError(f"{provider_label} returned no playful comment.")
        log_event("summary_provider_succeeded", provider=provider_label, key_points=len(core_points))
        return SummaryResult(
            title=title,
            overview=overview,
            core_points=core_points[:5],
            controversies=controversies[:3],
            action_suggestions=action_suggestions[:5],
            playful_comment=playful_comment,
            provider=provider_label,
        )

    def _render_summary_user_prompt(self, transcript: str) -> str:
        template = self.summary_user_prompt.strip()
        if "{transcript}" in template:
            return template.replace("{transcript}", transcript)
        return f"{template}\n\nTranscript:\n{transcript}"


def fallback_summary(transcript: str) -> SummaryResult:
    sentences = sentence_split(transcript)
    paragraphs = [part.strip() for part in transcript.split("\n\n") if part.strip()]
    title = sentences[0] if sentences else (transcript[:80].strip() or "未能生成标题。")
    overview = " ".join(sentences[:4]).strip() if sentences else (paragraphs[0] if paragraphs else transcript[:300].strip())
    core_points: list[str] = []
    for item in sentences[:8]:
        candidate = item.lstrip("- ").strip()
        if candidate and candidate not in core_points:
            core_points.append(candidate)
        if len(core_points) >= 5:
            break
    if not core_points:
        core_points = [title]
    controversies = [
        "逐字稿里没有特别明确的争议点，建议优先核查关键结论的证据来源。",
    ]
    action_suggestions = [
        "把视频提到的人名、机构名、论文名或政策名列出来，优先查一手来源。",
        "补读该主题的综述、教材章节或官方说明，确认基础概念是否准确。",
        "对关键数字、因果关系和结论做交叉验证，避免只依赖单一视频说法。",
    ]
    playful_comment = "这更像一张速读卡片，先拿来开路，别急着当终局答案。"
    return SummaryResult(
        title=title,
        overview=overview,
        core_points=core_points[:5],
        controversies=controversies,
        action_suggestions=action_suggestions,
        playful_comment=playful_comment,
        provider="rule-based fallback",
    )
