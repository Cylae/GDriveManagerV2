import io
import threading
import unittest
import urllib.error
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from gdsm.utils.retry import _retry_after, _safe_sleep, with_retry


class RetryTests(unittest.TestCase):
    def error(self, code=429, headers=None, body=b""):
        return urllib.error.HTTPError("", code, "test", headers or {}, io.BytesIO(body))

    @patch("gdsm.utils.retry._safe_sleep")
    def test_retry_on_429(self, sleep):
        func = Mock(side_effect=[self.error(), self.error(), "success"])
        self.assertEqual(with_retry(max_retries=3)(func)(), "success")
        self.assertEqual(func.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("gdsm.utils.retry._safe_sleep")
    def test_no_retry_on_404(self, sleep):
        func = Mock(side_effect=self.error(404))
        with self.assertRaises(urllib.error.HTTPError):
            with_retry()(func)()
        sleep.assert_not_called()

    @patch("gdsm.utils.retry._safe_sleep")
    def test_retry_after_header(self, sleep):
        func = Mock(side_effect=[self.error(headers={"Retry-After": "10"}), "ok"])
        self.assertEqual(with_retry(max_delay=5)(func)(), "ok")
        sleep.assert_called_once_with(5.0, None)

    @patch("gdsm.utils.retry.datetime")
    def test_retry_after_http_dates(self, clock):
        clock.now.return_value = datetime(2026, 10, 18, 4, 0, tzinfo=UTC)
        for value, expected in [
            ("Sun, 18 Oct 2026 04:00:10 GMT", 10),
            ("Sun, 18 Oct 2026 04:01:00 GMT", 15),
            ("Sun, 18 Oct 2026 03:00:00 GMT", 0),
            ("Sun, 18 Oct 2026 04:00:10", 10),
            (" 12 ", 12),
            ("invalid", None),
            ("-1", None),
            ("", None),
        ]:
            with self.subTest(value=value):
                self.assertEqual(_retry_after(value, 15), expected)

    @patch("gdsm.utils.retry._safe_sleep")
    @patch("gdsm.utils.retry.random.uniform", return_value=0.25)
    def test_invalid_header_falls_back_to_bounded_backoff(self, jitter, sleep):
        func = Mock(side_effect=[self.error(headers={"Retry-After": "invalid"}), "ok"])
        with_retry(base_delay=2)(func)()
        sleep.assert_called_once_with(2.25, None)

    @patch("gdsm.utils.retry._safe_sleep")
    def test_retry_on_403_structured_rate_limit(self, sleep):
        func = Mock(
            side_effect=[
                self.error(
                    403,
                    body=b'{"error":{"errors":[{"reason":"userRateLimitExceeded"}]}}',
                ),
                "ok",
            ]
        )
        self.assertEqual(with_retry()(func)(), "ok")
        self.assertEqual(func.call_count, 2)

    def test_permission_denied_body_remains_readable(self):
        error = self.error(403, body=b"permission denied")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            with_retry()(Mock(side_effect=error))()
        self.assertEqual(caught.exception.read(), b"permission denied")

    @patch("gdsm.utils.retry._safe_sleep")
    def test_retry_limit(self, sleep):
        func = Mock(side_effect=lambda: (_ for _ in ()).throw(self.error()))
        with self.assertRaises(urllib.error.HTTPError):
            with_retry(max_retries=2)(func)()
        self.assertEqual(func.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_pre_cancelled_call_performs_no_io(self):
        cancel = threading.Event()
        cancel.set()
        func = Mock()
        with self.assertRaises(InterruptedError):
            with_retry()(func)(cancel=cancel)
        func.assert_not_called()

    @patch("gdsm.utils.retry.time.sleep")
    def test_cancel_interrupts_backoff_immediately(self, sleep):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(InterruptedError):
            _safe_sleep(60, cancel)
        sleep.assert_not_called()

    def test_invalid_retry_configuration_is_rejected(self):
        for kwargs in (
            {"max_retries": -1},
            {"base_delay": -1},
            {"max_delay": float("nan")},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                with_retry(**kwargs)
