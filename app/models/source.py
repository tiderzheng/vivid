from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SourceInfo:
    raw_source: str
    platform: str
    title: str
