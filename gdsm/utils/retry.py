from __future__ import annotations
import time
import random
import urllib.error
from functools import wraps


def with_retry(max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 60.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    if e.code not in (408, 425, 429, 403, 500, 502, 503, 504):
                        raise

                    if e.code == 403:
                        # Check if it's a quota or rate limit error, otherwise don't retry 403
                        body = e.read().decode("utf-8", errors="ignore")
                        if (
                            "quota" not in body.lower()
                            and "rate limit" not in body.lower()
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

                    time.sleep(delay)
                    retries += 1
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    if retries >= max_retries:
                        raise
                    delay = min(
                        base_delay * (2**retries) + random.uniform(0, 1), max_delay
                    )
                    time.sleep(delay)
                    retries += 1

        return wrapper

    return decorator
