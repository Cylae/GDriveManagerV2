import unittest
import urllib.error
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

        decorated = with_retry(max_retries=3)(func)
        with patch('gdsm.utils.retry.time.sleep') as mock_sleep:
            decorated()

            self.assertEqual(func.call_count, 2)
            # _safe_sleep does delay*10 steps of 0.1 sleep, plus one remainder
            self.assertTrue(mock_sleep.call_count >= 10)

    def test_retry_after_header_http_date(self):
        from email.utils import formatdate
        import time
        future = time.time() + 5
        http_date = formatdate(timeval=future, localtime=False, usegmt=True)

        func = MagicMock()
        err = urllib.error.HTTPError(
            "", 429, "Too Many Requests", {"Retry-After": http_date}, None
        )
        func.side_effect = [err, "success"]

        decorated = with_retry(max_retries=3)(func)
        with patch('gdsm.utils.retry.time.sleep') as mock_sleep:
            decorated()

            self.assertEqual(func.call_count, 2)
            # Sleep calls for ~5 seconds is around 50 steps of 0.1
            self.assertTrue(mock_sleep.call_count >= 40)

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
