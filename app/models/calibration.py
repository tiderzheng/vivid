from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CalibrationResult:
    cn_text: str
    en_text: str
    provider: str = "scaffold"

    def to_payload(self) -> dict[str, object]:
        return {
            "cn_text": self.cn_text,
            "en_text": self.en_text,
            "provider": self.provider,
        }