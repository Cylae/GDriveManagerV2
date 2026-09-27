import unittest
import urllib.error
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

        import time
        from unittest.mock import patch

        with patch("gdsm.utils.retry.time.sleep") as mock_sleep:
            decorated = with_retry(max_retries=3)(func)
            decorated()

        # 1 second wait -> 10 iterations of 0.1s in _safe_sleep
        self.assertGreaterEqual(mock_sleep.call_count, 10)
        self.assertEqual(func.call_count, 2)

    def test_retry_after_http_date(self):
        func = MagicMock()
        import datetime
        import email.utils
        from unittest.mock import patch

        future_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=2)
        http_date = email.utils.format_datetime(future_date)

        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": http_date}, None
        )
        func.side_effect = [err, "success"]

        with patch("gdsm.utils.retry.time.sleep") as mock_sleep:
            decorated = with_retry(max_retries=3)(func)
            decorated()

        # At least 1s wait -> 10+ iterations of 0.1s in _safe_sleep
        # Time passes during test execution, so it's safer to check for >= 10
        self.assertGreaterEqual(mock_sleep.call_count, 10)
        self.assertEqual(func.call_count, 2)

    def test_retry_on_403_quota(self):
        func = MagicMock()
        import io

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
        import io

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


if __name__ == "__main__":
    unittest.main()
