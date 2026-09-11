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
            "", 429, "Too Many Requests", {"Retry-After": "10"}, None
        )
        func.side_effect = [err, "success"]

        from unittest.mock import patch
        with patch("gdsm.utils.retry.time.sleep") as mock_sleep:
            decorated = with_retry(max_retries=3)(func)
            decorated()

            mock_sleep.assert_called()
            # It will sleep 10 seconds total in chunks of 0.1s + remainder
            self.assertEqual(func.call_count, 2)

    def test_retry_after_http_date(self):
        func = MagicMock()

        import email.utils
        from datetime import datetime, timedelta, timezone

        future_dt = datetime.now(timezone.utc) + timedelta(seconds=15)
        date_str = email.utils.format_datetime(future_dt)

        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": date_str}, None
        )
        func.side_effect = [err, "success"]

        from unittest.mock import patch
        with patch("gdsm.utils.retry.time.sleep") as mock_sleep:
            decorated = with_retry(max_retries=3)(func)
            decorated()

            self.assertTrue(mock_sleep.called)
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
