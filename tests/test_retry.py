import email.utils
import unittest
import urllib.error
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

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

        start = time.time()
        decorated = with_retry(max_retries=3)(func)
        decorated()
        end = time.time()

        self.assertTrue(end - start >= 1.0)
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

    @patch('gdsm.utils.retry.time.sleep')
    def test_retry_after_http_date(self, mock_sleep):
        func = MagicMock()
        future_dt = datetime.now(UTC) + timedelta(seconds=10)
        http_date = email.utils.format_datetime(future_dt)
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": http_date}, None
        )
        func.side_effect = [err, "success"]
        decorated = with_retry(max_retries=3, max_delay=15.0)(func)
        decorated()

        # mock_sleep might be called multiple times due to _safe_sleep polling
        # But we verify total slept approx 10s by summing args
        total_sleep = sum(call[0][0] for call in mock_sleep.call_args_list)
        self.assertGreaterEqual(total_sleep, 9.0)
        self.assertLessEqual(total_sleep, 11.0)
        self.assertEqual(func.call_count, 2)

    @patch('gdsm.utils.retry.time.sleep')
    def test_retry_after_invalid_date(self, mock_sleep):
        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "invalid_date"}, None
        )
        func.side_effect = [err, "success"]
        decorated = with_retry(max_retries=3, base_delay=0.5)(func)
        decorated()
        total_sleep = sum(call[0][0] for call in mock_sleep.call_args_list)
        # Should fallback to base_delay * 1 + jitter = ~0.5s to 1.5s
        self.assertGreaterEqual(total_sleep, 0.5)
        self.assertLessEqual(total_sleep, 1.5)
        self.assertEqual(func.call_count, 2)


if __name__ == "__main__":
    unittest.main()
