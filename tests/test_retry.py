import email.utils
import io
import time
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from gdsm.utils.retry import with_retry


class RetryTests(unittest.TestCase):
    def test_retry_on_429(self):
        func = MagicMock()
        err = urllib.error.HTTPError("", 429, "Too Many Requests", {}, None)
        func.side_effect = [err, err, "success"]

        decorated = with_retry(max_retries=3, base_delay=0.01)(func)
        res = decorated()

        self.assertEqual(res, "success")
        self.assertEqual(func.call_count, 3)

    def test_no_retry_on_404(self):
        func = MagicMock()
        err = urllib.error.HTTPError("", 404, "Not Found", {}, None)
        func.side_effect = [err]

        decorated = with_retry(max_retries=3, base_delay=0.01)(func)
        with self.assertRaises(urllib.error.HTTPError):
            decorated()

        self.assertEqual(func.call_count, 1)

    def test_retry_after_header(self):
        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "1"}, None
        )
        func.side_effect = [err, "success"]


        start = time.time()
        decorated = with_retry(max_retries=3)(func)
        decorated()
        end = time.time()

        self.assertTrue(end - start >= 1.0)
        self.assertEqual(func.call_count, 2)

    def test_retry_on_403_quota(self):
        func = MagicMock()

        class R(io.BytesIO):
            def close(self):
                pass

        fp = R(b"quota exceeded")
        err = urllib.error.HTTPError("", 403, "Forbidden", {}, fp)
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3, base_delay=0.01)(func)
        res = decorated()

        self.assertEqual(res, "success")
        self.assertEqual(func.call_count, 2)

    def test_no_retry_on_403_other(self):
        func = MagicMock()

        class R(io.BytesIO):
            def close(self):
                pass

        fp = R(b"permission denied")
        err = urllib.error.HTTPError("", 403, "Forbidden", {}, fp)
        func.side_effect = [err]

        decorated = with_retry(max_retries=3, base_delay=0.01)(func)
        with self.assertRaises(urllib.error.HTTPError):
            decorated()

        self.assertEqual(func.call_count, 1)

    def test_retry_after_http_date(self):
        func = MagicMock()

        # Construct a Retry-After header a bit in the future

        # We need a delay of >=1s, but email.utils.format_datetime has only 1s precision
        # So we add 2 seconds, which will round down, giving us roughly 1 to 2 seconds delta
        future_dt = datetime.now(timezone.utc) + timedelta(seconds=2)
        http_date = email.utils.format_datetime(future_dt, usegmt=True)

        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": http_date}, None
        )
        func.side_effect = [err, "success"]


        start = time.time()
        decorated = with_retry(max_retries=3)(func)
        decorated()
        end = time.time()

        # It should sleep for approximately 1 to 2 seconds.
        # We test >= 1.0.
        self.assertTrue(end - start >= 1.0)
        self.assertEqual(func.call_count, 2)

if __name__ == "__main__":
    unittest.main()
