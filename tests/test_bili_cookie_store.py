from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.bili_cookie_store import (
    bili_cookie_store_path,
    load_bili_cookie,
    save_bili_cookie,
    save_bili_cookie_values,
)


def test_bili_cookie_store_saves_and_loads_project_local_secret(tmp_path: Path):
    cookie = "SESSDATA=demo; bili_jct=token; DedeUserID=42"

    path = save_bili_cookie(tmp_path, cookie, source="cli")

    assert path == tmp_path / "configs" / "secrets" / "bilibili_cookie.json"
    assert bili_cookie_store_path(tmp_path) == path
    assert load_bili_cookie(tmp_path) == cookie
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["cookie"] == cookie
    assert payload["source"] == "cli"
    assert payload["updated_at_utc"].endswith("Z")


def test_bili_cookie_store_ignores_missing_or_invalid_files(tmp_path: Path):
    assert load_bili_cookie(tmp_path) is None

    path = bili_cookie_store_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('{"cookie": "not-a-bili-cookie"}', encoding="utf-8")

    assert load_bili_cookie(tmp_path) is None


def test_bili_cookie_store_rejects_invalid_cookie_text(tmp_path: Path):
    with pytest.raises(ValueError, match="Bilibili cookie"):
        save_bili_cookie(tmp_path, "not-a-bili-cookie", source="cli")


def test_bili_cookie_store_saves_login_cookie_values(tmp_path: Path):
    path = save_bili_cookie_values(
        tmp_path,
        {
            "SESSDATA": "demo",
            "bili_jct": "csrf",
            "DedeUserID": "42",
            "DedeUserID__ckMd5": "md5",
            "ignored_empty": "",
        },
        source="qrcode",
    )

    assert path == bili_cookie_store_path(tmp_path)
    assert load_bili_cookie(tmp_path) == "SESSDATA=demo; bili_jct=csrf; DedeUserID=42; DedeUserID__ckMd5=md5"
