from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from ..exceptions import VividError


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_command(
    command: list[str],
    cwd: Path | None = None,
    retries: int = 1,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, retries + 1):
        try:
            return subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                env=env or command_env(),
                check=True,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2)
    assert last_error is not None
    detail = (last_error.stderr or last_error.stdout or "").strip()
    raise VividError(f"Command failed: {' '.join(command)}\n{detail}")
