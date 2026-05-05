from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

BILI_COOKIE_STORE_RELATIVE = Path("configs") / "secrets" / "bilibili_cookie.json"
BILI_COOKIE_SCHEMA_VERSION = 1
LOGIN_COOKIE_KEYS = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5")
_BILI_COOKIE_MARKERS = ("SESSDATA=", "bili_jct=")


def bili_cookie_store_path(repo_root: Path) -> Path:
    return repo_root / BILI_COOKIE_STORE_RELATIVE


def load_bili_cookie(repo_root: Path) -> str | None:
    path = bili_cookie_store_path(repo_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    cookie = payload.get("cookie")
    if not isinstance(cookie, str) or not _looks_like_bili_cookie(cookie):
        return None
    return cookie.strip()


def save_bili_cookie(repo_root: Path, cookie: str, source: str = "unknown") -> Path:
    cookie = cookie.strip()
    if not _looks_like_bili_cookie(cookie):
        raise ValueError("Bilibili cookie must include SESSDATA= or bili_jct=")
    path = bili_cookie_store_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": BILI_COOKIE_SCHEMA_VERSION,
        "updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cookie": cookie,
        "source": source,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _chmod_user_only(path)
    return path


def save_bili_cookie_values(repo_root: Path, values: Mapping[str, str], source: str = "unknown") -> Path:
    cookie = "; ".join(
        f"{name}={str(value).strip()}"
        for name in LOGIN_COOKIE_KEYS
        if (value := values.get(name)) is not None and str(value).strip()
    )
    return save_bili_cookie(repo_root, cookie, source=source)


def clear_bili_cookie(repo_root: Path) -> None:
    try:
        bili_cookie_store_path(repo_root).unlink()
    except FileNotFoundError:
        return


def _looks_like_bili_cookie(cookie: str) -> bool:
    value = cookie.strip()
    if not value:
        return False
    return any(marker in value for marker in _BILI_COOKIE_MARKERS)


def _chmod_user_only(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        path.chmod(0o600)
    except OSError:
        return
