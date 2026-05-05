from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any

from ..exceptions import VividError


DEFAULT_LOCK_STALE_SECONDS = 12 * 60 * 60


@dataclass(slots=True)
class QuickreadLock:
    data_dir: Path
    source: str
    stale_seconds: int = DEFAULT_LOCK_STALE_SECONDS
    path: Path | None = None
    token: str | None = None
    _fd: int | None = None

    def __enter__(self) -> QuickreadLock:
        lock_path = quickread_lock_path(self.data_dir)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = lock_path
        self.token = secrets.token_hex(16)
        payload = {
            "pid": os.getpid(),
            "source": self.source,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "token": self.token,
        }
        while True:
            try:
                self._fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                os.close(self._fd)
                self._fd = None
                return self
            except FileExistsError as exc:
                if _remove_stale_lock(lock_path, self.stale_seconds):
                    continue
                raise VividError(_lock_error_message(lock_path)) from exc

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        if self.path is not None:
            if not _lock_matches_token(self.path, self.token):
                return
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def quickread_lock_path(data_dir: Path) -> Path:
    return data_dir.expanduser().resolve() / ".vivid" / "quickread.lock"


def _lock_error_message(lock_path: Path) -> str:
    detail = _read_lock_payload(lock_path)
    pieces = [
        "Another Vivid quickread task is already running.",
        f"Lock file: {lock_path}",
    ]
    pid = detail.get("pid")
    source = detail.get("source")
    started_at = detail.get("started_at")
    if pid:
        pieces.append(f"PID: {pid}")
    if source:
        pieces.append(f"Source: {source}")
    if started_at:
        pieces.append(f"Started at: {started_at}")
    pieces.append("Wait for it to finish, or delete the lock file only after confirming no Vivid quickread is running.")
    return " ".join(pieces)


def _read_lock_payload(lock_path: Path) -> dict[str, Any]:
    try:
        text = lock_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _remove_stale_lock(lock_path: Path, stale_seconds: int) -> bool:
    payload = _read_lock_payload(lock_path)
    if not payload:
        return False
    pid = _int_or_none(payload.get("pid"))
    started_at = _datetime_or_none(payload.get("started_at"))
    if pid is not None:
        if _process_exists(pid):
            return False
        return _unlink_lock(lock_path)
    if started_at is not None:
        age = (datetime.now(timezone.utc) - started_at).total_seconds()
        if age < stale_seconds:
            return False
    return _unlink_lock(lock_path)


def _lock_matches_token(lock_path: Path, token: str | None) -> bool:
    if token is None:
        return False
    payload = _read_lock_payload(lock_path)
    return payload.get("token") == token


def _unlink_lock(lock_path: Path) -> bool:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _datetime_or_none(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
