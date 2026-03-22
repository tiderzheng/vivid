from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, init=False)
class SummaryResult:
    title: str
    overview: str
    core_points: list[str] = field(default_factory=list)
    controversies: list[str] = field(default_factory=list)
    action_suggestions: list[str] = field(default_factory=list)
    playful_comment: str = ""
    provider: str = "scaffold"

    def __init__(
        self,
        *,
        title: str | None = None,
        overview: str | None = None,
        core_points: list[str] | None = None,
        controversies: list[str] | None = None,
        action_suggestions: list[str] | None = None,
        playful_comment: str | None = None,
        provider: str = "scaffold",
        one_line: str | None = None,
        detailed: str | None = None,
        key_points: list[str] | None = None,
    ) -> None:
        self.title = str(title or one_line or "").strip()
        self.overview = str(overview or detailed or "").strip()
        self.core_points = [str(item).strip() for item in (core_points or key_points or []) if str(item).strip()]
        self.controversies = [str(item).strip() for item in (controversies or []) if str(item).strip()]
        self.action_suggestions = [str(item).strip() for item in (action_suggestions or []) if str(item).strip()]
        self.playful_comment = str(playful_comment or "").strip()
        self.provider = str(provider or "scaffold").strip() or "scaffold"

    @property
    def one_line(self) -> str:
        return self.title

    @property
    def key_points(self) -> list[str]:
        return list(self.core_points)

    @property
    def detailed(self) -> str:
        blocks: list[str] = []
        if self.overview:
            blocks.extend(["内容概览", self.overview])
        if self.core_points:
            blocks.extend(["核心观点", *[f"- {item}" for item in self.core_points]])
        if self.controversies:
            blocks.extend(["争议点", *[f"- {item}" for item in self.controversies]])
        if self.action_suggestions:
            blocks.extend(["行动建议", *[f"- {item}" for item in self.action_suggestions]])
        if self.playful_comment:
            blocks.extend(["俏皮点评", self.playful_comment])
        return "\n".join(blocks).strip()

    def to_payload(self) -> dict[str, object]:
        return {
            "title": self.title,
            "overview": self.overview,
            "core_points": list(self.core_points),
            "controversies": list(self.controversies),
            "action_suggestions": list(self.action_suggestions),
            "playful_comment": self.playful_comment,
            "one_line": self.one_line,
            "detailed": self.detailed,
            "key_points": self.key_points,
            "provider": self.provider,
        }
