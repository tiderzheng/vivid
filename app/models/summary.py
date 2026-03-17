from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SummaryResult:
    one_line: str
    detailed: str
    key_points: list[str] = field(default_factory=list)
    provider: str = "scaffold"
