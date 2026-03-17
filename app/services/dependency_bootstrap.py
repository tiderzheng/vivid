from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from typing import Any

from ..exceptions import VividError

DEFAULT_PIP_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"


def ensure_opencv_dependency(*, raise_on_failure: bool = True) -> dict[str, Any]:
    if _module_available("cv2"):
        return {
            "ok": True,
            "module": "cv2",
            "package": "opencv-python",
            "already_available": True,
            "installed": False,
            "index_url": _pip_index_url(),
        }

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "opencv-python",
        "-i",
        _pip_index_url(),
    ]
    result = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_command_env(),
    )
    available = _module_available("cv2")
    payload = {
        "ok": result.returncode == 0 and available,
        "module": "cv2",
        "package": "opencv-python",
        "already_available": False,
        "installed": available,
        "index_url": _pip_index_url(),
        "command": command,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "returncode": result.returncode,
    }
    if payload["ok"] or not raise_on_failure:
        return payload
    detail = payload["stderr"] or payload["stdout"] or "unknown pip error"
    raise VividError(f"Failed to auto-install opencv-python: {detail}")


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _pip_index_url() -> str:
    return os.environ.get("VIVID_PIP_INDEX_URL", DEFAULT_PIP_INDEX_URL)


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env
