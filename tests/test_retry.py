import unittest
import urllib.error
import datetime
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

    @patch('gdsm.utils.retry._safe_sleep')
    def test_retry_after_header(self, mock_sleep):
        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "1"}, None
        )
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3)(func)
        decorated()

        mock_sleep.assert_called_with(1.0, None)
        self.assertEqual(func.call_count, 2)

    @patch('gdsm.utils.retry._safe_sleep')
    @patch('gdsm.utils.retry.datetime')
    def test_retry_after_http_date(self, mock_datetime, mock_sleep):
        # Set "now" to a fixed time
        mock_now = datetime.datetime(2023, 10, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.timezone = datetime.timezone

        # HTTP-date for 5 seconds in the future
        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": "Sun, 01 Oct 2023 12:00:05 GMT"}, None
        )
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3)(func)
        decorated()

        mock_sleep.assert_called_with(5.0, None)
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
