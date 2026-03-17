from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_call(func: Callable[[], T], retries: int = 2, delay_seconds: float = 1.0) -> T:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return func()
        except Exception as error:  # noqa: BLE001
            last_error = error
            if attempt >= retries:
                break
            time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error
