from __future__ import annotations
import time
import random
import urllib.error
import io
from functools import wraps


def with_retry(max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            cancel = kwargs.get("cancel", None)

            def safe_sleep(delay):
                steps = int(delay * 10)
                for _ in range(steps):
                    if cancel and cancel.is_set():
                        raise InterruptedError("cancelled")
                    time.sleep(0.1)
                time.sleep(delay - (steps * 0.1))
                if cancel and cancel.is_set():
                    raise InterruptedError("cancelled")

            while True:
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    if e.code not in (408, 425, 429, 403, 500, 502, 503, 504):
                        raise

                    if e.code == 403:
                        body = e.read()
                        text_body = body.decode("utf-8", errors="ignore")
                        # Reconstruct the stream so upstream can read it again
                        if hasattr(e, "fp") and e.fp:
                            e.fp = io.BytesIO(body)

                        if (
                            "quota" not in text_body.lower()
                            and "rate limit" not in text_body.lower()
                        ):
                            raise

                    if retries >= max_retries:
                        raise

                    retry_after = e.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        delay = min(int(retry_after), max_delay)
                    else:
                        delay = min(
                            base_delay * (2**retries) + random.uniform(0, 1), max_delay
                        )

                    safe_sleep(delay)
                    retries += 1
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    if retries >= max_retries:
                        raise
                    delay = min(
                        base_delay * (2**retries) + random.uniform(0, 1), max_delay
                    )
                    safe_sleep(delay)
                    retries += 1

        return wrapper

    return decorator
