from __future__ import annotations

from pathlib import Path

import pytest

from app.services.bili_auth import (
    BiliAuthError,
    BiliQrCodeExpiredError,
    BiliQrCodePending,
    BiliQrCodeStatus,
    BiliQrCodeWaitingForConfirmation,
    generate_bili_qrcode,
    get_bili_login_status,
    logout_bili,
    poll_bili_qrcode,
)
from app.services.bili_cookie_store import load_bili_cookie, save_bili_cookie


class FakeCookieJar:
    def __init__(self, values: dict[str, str]):
        self.values = values

    def get(self, name: str, default: str = "", domain: str | None = None):
        return self.values.get(name, default)


class FakeResponse:
    def __init__(self, payload: dict, cookies: dict[str, str] | None = None):
        self.payload = payload
        self.cookies = FakeCookieJar(cookies or {})

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.requests: list[tuple[str, str, dict]] = []
        self.cookies = FakeCookieJar({})

    def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.responses[url]

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.responses[url]


def test_generate_bili_qrcode_returns_key_and_url():
    session = FakeSession(
        {
            "https://passport.bilibili.com/x/passport-login/web/qrcode/generate": FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "url": "https://passport.bilibili.com/h5-app/passport/login/scan?navhide=1&qrcode_key=abc",
                        "qrcode_key": "abc",
                    },
                }
            )
        }
    )

    result = generate_bili_qrcode(session=session)

    assert result.qrcode_key == "abc"
    assert result.url.startswith("https://passport.bilibili.com/")
    assert result.poll_status == BiliQrCodeStatus.WAITING_FOR_SCAN
    method, url, kwargs = session.requests[0]
    assert method == "GET"
    assert url == "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    assert kwargs["params"]["source"] == "main-fe-header"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (86101, BiliQrCodePending),
        (86090, BiliQrCodeWaitingForConfirmation),
        (86038, BiliQrCodeExpiredError),
    ],
)
def test_poll_bili_qrcode_reports_non_success_states(tmp_path: Path, code: int, expected: type[Exception]):
    session = FakeSession(
        {
            "https://passport.bilibili.com/x/passport-login/web/qrcode/poll": FakeResponse(
                {"code": 0, "data": {"code": code, "message": "state"}}
            )
        }
    )

    with pytest.raises(expected):
        poll_bili_qrcode(tmp_path, "abc", session=session)

    assert load_bili_cookie(tmp_path) is None


def test_poll_bili_qrcode_success_persists_login_cookies(tmp_path: Path):
    session = FakeSession(
        {
            "https://passport.bilibili.com/x/passport-login/web/qrcode/poll": FakeResponse(
                {"code": 0, "data": {"code": 0, "message": "ok"}},
                cookies={
                    "SESSDATA": "demo",
                    "bili_jct": "csrf",
                    "DedeUserID": "42",
                    "DedeUserID__ckMd5": "md5",
                },
            )
        }
    )

    result = poll_bili_qrcode(tmp_path, "abc", session=session)

    assert result.status == BiliQrCodeStatus.SUCCESS
    assert result.saved is True
    assert load_bili_cookie(tmp_path) == "SESSDATA=demo; bili_jct=csrf; DedeUserID=42; DedeUserID__ckMd5=md5"


def test_poll_bili_qrcode_success_persists_login_cookies_from_payload_url(tmp_path: Path):
    session = FakeSession(
        {
            "https://passport.bilibili.com/x/passport-login/web/qrcode/poll": FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "code": 0,
                        "message": "ok",
                        "url": (
                            "https://www.bilibili.com/?"
                            "SESSDATA=demo-url&bili_jct=csrf-url&"
                            "DedeUserID=42&DedeUserID__ckMd5=md5-url"
                        ),
                    },
                }
            )
        }
    )

    result = poll_bili_qrcode(tmp_path, "abc", session=session)

    assert result.status == BiliQrCodeStatus.SUCCESS
    assert result.saved is True
    assert load_bili_cookie(tmp_path) == (
        "SESSDATA=demo-url; bili_jct=csrf-url; DedeUserID=42; DedeUserID__ckMd5=md5-url"
    )


def test_poll_bili_qrcode_requires_sessdata_cookie(tmp_path: Path):
    session = FakeSession(
        {
            "https://passport.bilibili.com/x/passport-login/web/qrcode/poll": FakeResponse(
                {"code": 0, "data": {"code": 0, "message": "ok"}},
                cookies={"bili_jct": "csrf"},
            )
        }
    )

    with pytest.raises(BiliAuthError):
        poll_bili_qrcode(tmp_path, "abc", session=session)

    assert load_bili_cookie(tmp_path) is None


def test_get_bili_login_status_uses_persisted_cookie_without_exposing_it(tmp_path: Path):
    save_bili_cookie(tmp_path, "SESSDATA=demo; bili_jct=csrf; DedeUserID=42", source="test")
    session = FakeSession(
        {
            "https://api.bilibili.com/x/web-interface/nav": FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "isLogin": True,
                        "uname": "tester",
                        "mid": 42,
                        "wbi_img": {
                            "img_url": "https://i0.hdslb.com/bfs/wbi/imgkey.png",
                            "sub_url": "https://i0.hdslb.com/bfs/wbi/subkey.png",
                        },
                    },
                }
            )
        }
    )

    status = get_bili_login_status(tmp_path, session=session)

    assert status.is_login is True
    assert status.uname == "tester"
    assert status.mid == 42
    assert status.cookie_present is True
    assert "SESSDATA" not in status.to_public_dict()
    assert session.requests[0][2]["headers"]["Cookie"] == "SESSDATA=demo; bili_jct=csrf; DedeUserID=42"


def test_get_bili_login_status_treats_not_logged_in_api_code_as_expired(tmp_path: Path):
    save_bili_cookie(tmp_path, "SESSDATA=demo; bili_jct=csrf; DedeUserID=42", source="test")
    session = FakeSession(
        {
            "https://api.bilibili.com/x/web-interface/nav": FakeResponse(
                {"code": -101, "message": "账号未登录"}
            )
        }
    )

    status = get_bili_login_status(tmp_path, session=session)

    assert status.is_login is False
    assert status.cookie_present is True
    assert status.expired is True
    assert status.to_public_dict()["uname"] is None


def test_logout_bili_posts_csrf_and_clears_cookie(tmp_path: Path):
    save_bili_cookie(tmp_path, "SESSDATA=demo; bili_jct=csrf; DedeUserID=42", source="test")
    session = FakeSession(
        {
            "https://passport.bilibili.com/login/exit/v2": FakeResponse(
                {"code": 0, "message": "ok"}
            )
        }
    )

    result = logout_bili(tmp_path, session=session)

    assert result.ok is True
    assert load_bili_cookie(tmp_path) is None
    method, url, kwargs = session.requests[0]
    assert method == "POST"
    assert url == "https://passport.bilibili.com/login/exit/v2"
    assert kwargs["params"]["biliCSRF"] == "csrf"
    assert kwargs["headers"]["Cookie"] == "SESSDATA=demo; bili_jct=csrf; DedeUserID=42"


def test_logout_bili_clears_local_cookie_when_csrf_missing(tmp_path: Path):
    save_bili_cookie(tmp_path, "SESSDATA=legacy-only", source="test")
    session = FakeSession({})

    result = logout_bili(tmp_path, session=session)

    assert result.ok is True
    assert result.cleared is True
    assert load_bili_cookie(tmp_path) is None
    assert session.requests == []
