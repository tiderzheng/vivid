from __future__ import annotations

import os
import shutil
from pathlib import Path


def inspect_ffmpeg(
    *,
    preferred: str | None = None,
    repo_root: Path | None = None,
    tools_root: Path | None = None,
) -> dict:
    candidates = candidate_ffmpeg_bins(preferred=preferred, repo_root=repo_root, tools_root=tools_root)
    for source, candidate in candidates:
        resolved = _resolve_candidate(candidate)
        if resolved:
            return {
                "available": True,
                "source": source,
                "preferred": preferred,
                "resolved": resolved,
                "candidates": [value for _, value in candidates],
            }
    return {
        "available": False,
        "source": None,
        "preferred": preferred,
        "resolved": None,
        "candidates": [value for _, value in candidates],
    }


def resolve_ffmpeg_bin(
    preferred: str | None = None,
    *,
    repo_root: Path | None = None,
    tools_root: Path | None = None,
) -> str:
    inspection = inspect_ffmpeg(preferred=preferred, repo_root=repo_root, tools_root=tools_root)
    return inspection["resolved"] or (preferred or "ffmpeg")


def candidate_ffmpeg_bins(
    *,
    preferred: str | None = None,
    repo_root: Path | None = None,
    tools_root: Path | None = None,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(source: str, value: str | Path | None) -> None:
        if value is None:
            return
        text = str(value).strip()
        if not text:
            return
        key = text.lower() if os.name == "nt" else text
        if key in seen:
            return
        seen.add(key)
        candidates.append((source, text))

    add("preferred", preferred)
    env_value = os.environ.get("VIVID_FFMPEG_BIN")
    add("env", env_value)

    for root_name, root in (("repo", repo_root), ("tools", tools_root)):
        if root is None:
            continue
        root = Path(root)
        for candidate in _bundled_candidates(root):
            add(f"{root_name}_bundled", candidate)

    add("path", "ffmpeg")
    return candidates


def _bundled_candidates(root: Path) -> list[Path]:
    names = ["ffmpeg.exe", "ffmpeg"] if os.name == "nt" else ["ffmpeg"]
    candidates: list[Path] = []
    direct_dirs = [
        root / "vendor" / "ffmpeg" / "bin",
        root / ".tools" / "ffmpeg" / "bin",
        root / "ffmpeg" / "bin",
        root / "bin",
    ]
    for directory in direct_dirs:
        for name in names:
            candidates.append(directory / name)
    for match in sorted(root.glob("ffmpeg*")):
        if not match.is_dir():
            continue
        for name in names:
            candidates.append(match / "bin" / name)
            candidates.append(match / name)
    return candidates


def _resolve_candidate(candidate: str) -> str | None:
    path = Path(candidate).expanduser()
    if path.exists():
        return str(path.resolve())
    resolved = shutil.which(candidate)
    if resolved:
        return str(Path(resolved).resolve())
    return None
