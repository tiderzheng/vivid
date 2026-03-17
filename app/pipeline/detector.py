from __future__ import annotations

from pathlib import Path


def detect_platform(source: str, forced_platform: str | None = None) -> str:
    if forced_platform:
        return forced_platform
    if Path(source).exists():
        return "local"
    lowered = source.lower()
    if "bilibili.com" in lowered or "b23.tv" in lowered or "bili2233.cn" in lowered:
        return "bilibili"
    if "douyin.com" in lowered or "iesdouyin.com" in lowered or "v.douyin.com" in lowered:
        return "douyin"
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return "youtube"
    return "generic"
