"""Bounded, cancellable retries for transient Google API errors."""

from __future__ import annotations

import io
import json
import math
import random
import threading
import time
import urllib.error
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import wraps

_RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
_RATE_REASONS = {
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "quotaExceeded",
    "dailyLimitExceeded",
}


def _safe_sleep(delay: float, cancel: threading.Event | None) -> None:
    if cancel is not None:
        if cancel.wait(delay):
            raise InterruptedError("cancelled")
    else:
        time.sleep(delay)


def _retry_after(value: str | None, maximum: float) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        if value.isascii() and value.isdecimal():
            return min(float(value), maximum)
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        return min(max(0.0, (date - datetime.now(UTC)).total_seconds()), maximum)
    except (ValueError, TypeError, OverflowError):
        return None


def _transient(error: urllib.error.HTTPError) -> bool:
    if error.code != 403:
        return error.code in _RETRYABLE
    body = error.read()
    # HTTPError delegates reads through its file wrapper, not only its fp field.
    error.file = error.fp = io.BytesIO(body)
    error.__dict__.pop("read", None)
    try:
        payload = json.loads(body)
        reasons = {
            row.get("reason") for row in payload.get("error", {}).get("errors", [])
        }
        if reasons & _RATE_REASONS:
            return True
    except (ValueError, TypeError, AttributeError):
        pass
    text = body.decode("utf-8", errors="replace").lower()
    return "quota" in text or "rate limit" in text or "ratelimitexceeded" in text


def with_retry(max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
    if (
        max_retries < 0
        or not math.isfinite(base_delay)
        or not math.isfinite(max_delay)
        or min(base_delay, max_delay) < 0
    ):
        raise ValueError("retry counts and delays must be finite and non-negative")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cancel = kwargs.get("cancel")
            for attempt in range(max_retries + 1):
                if cancel is not None and cancel.is_set():
                    raise InterruptedError("cancelled")
                try:
                    return func(*args, **kwargs)
                except InterruptedError:
                    raise
                except urllib.error.HTTPError as error:
                    if not _transient(error) or attempt == max_retries:
                        raise
                    delay = _retry_after(error.headers.get("Retry-After"), max_delay)
                    error.close()
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    if attempt == max_retries:
                        raise
                    delay = None
                if delay is None:
                    delay = min(
                        base_delay * (2 ** min(attempt, 60)) + random.uniform(0, 1),
                        max_delay,
                    )
                _safe_sleep(delay, cancel)
            raise AssertionError("unreachable retry state")

        return wrapper

    return decorator
