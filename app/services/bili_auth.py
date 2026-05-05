from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from .bili_cookie_store import clear_bili_cookie, load_bili_cookie, save_bili_cookie_values

QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
LOGOUT_URL = "https://passport.bilibili.com/login/exit/v2"
LOGIN_COOKIE_KEYS = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BiliQrCodeStatus(IntEnum):
    SUCCESS = 0
    WAITING_FOR_SCAN = 86101
    WAITING_FOR_CONFIRMATION = 86090
    EXPIRED = 86038

    @property
    def label(self) -> str:
        labels = {
            BiliQrCodeStatus.SUCCESS: "success",
            BiliQrCodeStatus.WAITING_FOR_SCAN: "waiting_for_scan",
            BiliQrCodeStatus.WAITING_FOR_CONFIRMATION: "waiting_for_confirmation",
            BiliQrCodeStatus.EXPIRED: "expired",
        }
        return labels[self]


class BiliAuthError(RuntimeError):
    pass


class BiliQrCodePending(BiliAuthError):
    pass


class BiliQrCodeWaitingForConfirmation(BiliAuthError):
    pass


class BiliQrCodeExpiredError(BiliAuthError):
    pass


@dataclass(slots=True)
class BiliQrCodeInfo:
    qrcode_key: str
    url: str
    poll_status: BiliQrCodeStatus = BiliQrCodeStatus.WAITING_FOR_SCAN
    qrcode_svg: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "qrcode_key": self.qrcode_key,
            "url": self.url,
            "status": self.poll_status.label,
        }
        if self.qrcode_svg:
            payload["qrcode_svg"] = self.qrcode_svg
        return payload


@dataclass(slots=True)
class BiliQrCodePollResult:
    status: BiliQrCodeStatus
    message: str = ""
    saved: bool = False

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.label,
            "message": self.message,
            "saved": self.saved,
        }


@dataclass(slots=True)
class BiliLoginStatus:
    is_login: bool
    cookie_present: bool
    uname: str | None = None
    mid: int | None = None
    expired: bool = False
    img_key: str | None = None
    sub_key: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "is_login": self.is_login,
            "cookie_present": self.cookie_present,
            "uname": self.uname,
            "mid": self.mid,
            "expired": self.expired,
            "img_key": self.img_key,
            "sub_key": self.sub_key,
        }


@dataclass(slots=True)
class BiliLogoutResult:
    ok: bool
    cleared: bool
    message: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "cleared": self.cleared, "message": self.message}


def generate_bili_qrcode(*, session: requests.Session | None = None) -> BiliQrCodeInfo:
    client = session or requests.Session()
    response = client.get(
        QR_GENERATE_URL,
        params={
            "source": "main-fe-header",
            "go_url": "https://www.bilibili.com/",
            "web_location": "333.1007",
        },
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    data = _json_payload(response)
    _ensure_api_ok(data)
    payload = _payload_data(data)
    url = _required_text(payload, "url")
    qrcode_key = _required_text(payload, "qrcode_key")
    return BiliQrCodeInfo(qrcode_key=qrcode_key, url=url, qrcode_svg=_build_qrcode_svg(url))


def poll_bili_qrcode(repo_root: Path, qrcode_key: str, *, session: requests.Session | None = None) -> BiliQrCodePollResult:
    client = session or requests.Session()
    response = client.get(
        QR_POLL_URL,
        params={"qrcode_key": qrcode_key},
        headers=_headers(),
        timeout=15,
    )
    response.raise_for_status()
    data = _json_payload(response)
    _ensure_api_ok(data)
    payload = _payload_data(data)
    code = int(payload.get("code", -1))
    message = str(payload.get("message") or "")
    if code == BiliQrCodeStatus.WAITING_FOR_SCAN:
        raise BiliQrCodePending(message or "waiting for scan")
    if code == BiliQrCodeStatus.WAITING_FOR_CONFIRMATION:
        raise BiliQrCodeWaitingForConfirmation(message or "waiting for confirmation")
    if code == BiliQrCodeStatus.EXPIRED:
        raise BiliQrCodeExpiredError(message or "qrcode expired")
    if code != BiliQrCodeStatus.SUCCESS:
        raise BiliAuthError(f"unknown qrcode status: {code}")
    cookie_values = _extract_login_cookies(response, client, payload)
    save_bili_cookie_values(repo_root, cookie_values, source="qrcode")
    return BiliQrCodePollResult(status=BiliQrCodeStatus.SUCCESS, message=message, saved=True)


def get_bili_login_status(repo_root: Path, *, session: requests.Session | None = None) -> BiliLoginStatus:
    cookie = load_bili_cookie(repo_root)
    if not cookie:
        return BiliLoginStatus(is_login=False, cookie_present=False)
    client = session or requests.Session()
    response = client.get(NAV_URL, headers=_headers(cookie), timeout=15)
    response.raise_for_status()
    data = _json_payload(response)
    if data.get("code") == -101:
        return BiliLoginStatus(is_login=False, cookie_present=True, expired=True)
    _ensure_api_ok(data)
    payload = _payload_data(data)
    is_login = bool(payload.get("isLogin"))
    wbi_img = payload.get("wbi_img") if isinstance(payload.get("wbi_img"), dict) else {}
    return BiliLoginStatus(
        is_login=is_login,
        cookie_present=True,
        uname=_optional_text(payload.get("uname")),
        mid=_optional_int(payload.get("mid")),
        expired=not is_login,
        img_key=_url_stem(_optional_text(wbi_img.get("img_url"))),
        sub_key=_url_stem(_optional_text(wbi_img.get("sub_url"))),
    )


def logout_bili(repo_root: Path, *, session: requests.Session | None = None) -> BiliLogoutResult:
    cookie = load_bili_cookie(repo_root)
    if not cookie:
        clear_bili_cookie(repo_root)
        return BiliLogoutResult(ok=True, cleared=False, message="no persisted cookie")
    csrf = _parse_cookie_header(cookie).get("bili_jct")
    if not csrf:
        clear_bili_cookie(repo_root)
        return BiliLogoutResult(
            ok=True,
            cleared=True,
            message="persisted Bilibili cookie is missing bili_jct; cleared local cookie",
        )
    client = session or requests.Session()
    response = client.post(
        LOGOUT_URL,
        params={"biliCSRF": csrf},
        headers=_headers(cookie),
        timeout=15,
    )
    response.raise_for_status()
    data = _json_payload(response)
    _ensure_api_ok(data)
    clear_bili_cookie(repo_root)
    return BiliLogoutResult(ok=True, cleared=True, message=str(data.get("message") or "ok"))


def _headers(cookie: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _json_payload(response: requests.Response) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise BiliAuthError("Bilibili auth API returned a non-object payload")
    return payload


def _ensure_api_ok(payload: dict[str, Any]) -> None:
    if payload.get("code") != 0:
        raise BiliAuthError(str(payload.get("message") or payload.get("code") or "Bilibili auth API failed"))


def _payload_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise BiliAuthError("Bilibili auth API response is missing data")
    return data


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BiliAuthError(f"Bilibili auth API response is missing {key}")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_login_cookies(response: Any, session: Any, payload: dict[str, Any] | None = None) -> dict[str, str]:
    values = _extract_cookie_values_from_url(_optional_text((payload or {}).get("url")))
    for name in LOGIN_COOKIE_KEYS:
        if values.get(name):
            continue
        value = _cookie_value(getattr(response, "cookies", None), name) or _cookie_value(getattr(session, "cookies", None), name)
        if value:
            values[name] = value
    if not values.get("SESSDATA"):
        raise BiliAuthError("login succeeded but Bilibili did not return SESSDATA")
    return values


def _extract_cookie_values_from_url(url: str | None) -> dict[str, str]:
    if not url:
        return {}
    parsed = urlparse(url)
    candidates = [parsed.query]
    if parsed.fragment:
        candidates.append(urlparse(parsed.fragment).query)
        candidates.append(parsed.fragment)
    if "=" in url and not parsed.query:
        candidates.append(url)

    values: dict[str, str] = {}
    for candidate in candidates:
        if not candidate:
            continue
        query = parse_qs(candidate.lstrip("?"), keep_blank_values=False)
        for name in LOGIN_COOKIE_KEYS:
            if name in values:
                continue
            entries = query.get(name)
            if entries:
                value = _optional_text(entries[-1])
                if value:
                    values[name] = value
    return values


def _cookie_value(cookie_jar: Any, name: str) -> str | None:
    if cookie_jar is None or not hasattr(cookie_jar, "get"):
        return None
    try:
        value = cookie_jar.get(name, domain=".bilibili.com")
    except TypeError:
        value = cookie_jar.get(name)
    if not value:
        try:
            value = cookie_jar.get(name)
        except TypeError:
            value = None
    return _optional_text(value)


def _parse_cookie_header(cookie: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in cookie.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            values[key] = value
    return values


def _url_stem(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    stem = Path(path).stem
    return stem or None


def _build_qrcode_svg(url: str) -> str | None:
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return None
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage)
    return image.to_string(encoding="unicode")
