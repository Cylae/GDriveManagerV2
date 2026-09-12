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

    @unittest.mock.patch("gdsm.utils.retry.time.sleep")
    def test_retry_after_header_seconds(self, mock_sleep):
        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "2"}, None
        )
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3)(func)
        res = decorated()

        self.assertEqual(res, "success")
        self.assertEqual(func.call_count, 2)
        # Should be called 20 times with 0.1 for the 2.0s delay, plus the remaining 0.0 delay
        mock_sleep.assert_called()
        self.assertGreaterEqual(mock_sleep.call_count, 20)

    @unittest.mock.patch("gdsm.utils.retry.time.sleep")
    @unittest.mock.patch("gdsm.utils.retry.datetime")
    def test_retry_after_header_http_date(self, mock_datetime, mock_sleep):
        import datetime
        now = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        mock_datetime.datetime.now.return_value = now
        mock_datetime.timezone = datetime.timezone

        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "Thu, 01 Jan 2026 12:00:03 GMT"}, None
        )
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3)(func)
        res = decorated()

        self.assertEqual(res, "success")
        self.assertEqual(func.call_count, 2)
        mock_sleep.assert_called()
        self.assertGreaterEqual(mock_sleep.call_count, 30) # 3 seconds delay

    @unittest.mock.patch("gdsm.utils.retry.time.sleep")
    @unittest.mock.patch("gdsm.utils.retry.datetime")
    def test_retry_after_header_http_date_past(self, mock_datetime, mock_sleep):
        import datetime
        now = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        mock_datetime.datetime.now.return_value = now
        mock_datetime.timezone = datetime.timezone

        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "Thu, 01 Jan 2025 12:00:00 GMT"}, None
        )
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3)(func)
        res = decorated()

        self.assertEqual(res, "success")
        self.assertEqual(func.call_count, 2)
        mock_sleep.assert_called_with(0.0) # 0 seconds delay since it's in the past

    @unittest.mock.patch("gdsm.utils.retry.time.sleep")
    def test_retry_after_header_http_date_malformed(self, mock_sleep):
        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "Not a date"}, None
        )
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3, base_delay=0.01)(func)
        res = decorated()

        self.assertEqual(res, "success")
        self.assertEqual(func.call_count, 2)
        mock_sleep.assert_called()

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
