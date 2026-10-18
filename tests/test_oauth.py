import io
import json
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth, OAuthCallbackHandler, OAuthCallbackServer


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.oauth = GoogleOAuth(Settings(client_id="test-client"), Mock())

    @patch("gdsm.services.oauth.delete_secret")
    def test_logout_resets_state_and_deletes_secret(self, delete):
        self.oauth.access, self.oauth.expiry = ("cached", 1234567890)
        self.oauth.logout()
        self.assertEqual((self.oauth.access, self.oauth.expiry), ("", 0))
        delete.assert_called_once_with("refresh_token")

    @patch("gdsm.services.oauth.load_secret", return_value="refresh")
    @patch("gdsm.services.oauth.urllib.request.urlopen")
    def test_thread_safe_token_refresh(self, urlopen, load):
        response = Mock()
        response.__enter__ = Mock(
            return_value=io.BytesIO(b'{"access_token":"fresh","expires_in":3600}')
        )
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response
        barrier = threading.Barrier(8)

        def request():
            barrier.wait(timeout=3)
            return self.oauth.token()

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(request) for _ in range(8)]
            self.assertEqual(
                [future.result(timeout=5) for future in futures], ["fresh"] * 8
            )
        urlopen.assert_called_once()
        load.assert_called_once()

    @patch("gdsm.services.oauth.load_secret", return_value=None)
    def test_interactive_sign_in_is_also_serialized(self, load):
        barrier = threading.Barrier(6)

        def interactive():
            with self.oauth._lock:
                self.oauth.access, self.oauth.expiry = ("interactive", 9999999999)
            return "interactive"

        def request():
            barrier.wait(timeout=3)
            return self.oauth.token()

        with patch.object(
            self.oauth, "_interactive", side_effect=interactive
        ) as browser:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = [pool.submit(request) for _ in range(6)]
                self.assertEqual(
                    [f.result(timeout=5) for f in futures], ["interactive"] * 6
                )
            browser.assert_called_once()

    @patch("gdsm.services.oauth.save_secret")
    @patch("gdsm.services.oauth.delete_secret")
    @patch("gdsm.services.oauth.load_secret", return_value="old")
    def test_logout_waits_for_refresh_and_removes_rotated_secret(
        self, load, delete, save
    ):
        entered, release, logout_started = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )
        response = Mock()
        response.__enter__ = Mock(
            return_value=io.BytesIO(
                json.dumps(
                    {
                        "access_token": "fresh",
                        "refresh_token": "rotated",
                        "expires_in": 3600,
                    }
                ).encode()
            )
        )
        response.__exit__ = Mock(return_value=False)

        def urlopen(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("test synchronization timed out")
            return response

        def logout():
            logout_started.set()
            self.oauth.logout()

        with (
            patch("gdsm.services.oauth.urllib.request.urlopen", side_effect=urlopen),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            token = pool.submit(self.oauth.token)
            self.assertTrue(entered.wait(3))
            stopped = pool.submit(logout)
            self.assertTrue(logout_started.wait(3))
            try:
                self.assertFalse(stopped.done())
            finally:
                release.set()
            self.assertEqual(token.result(timeout=3), "fresh")
            stopped.result(timeout=3)
        save.assert_called_once_with("refresh_token", "rotated")
        delete.assert_called_once_with("refresh_token")
        self.assertEqual((self.oauth.access, self.oauth.expiry), ("", 0))

    @patch("gdsm.services.oauth.load_secret", return_value="old")
    def test_network_failure_does_not_open_browser(self, load):
        with (
            patch.object(
                self.oauth, "_exchange", side_effect=urllib.error.URLError("offline")
            ),
            patch.object(self.oauth, "_interactive") as browser,
        ):
            with self.assertRaises(urllib.error.URLError):
                self.oauth.token()
            browser.assert_not_called()

    @patch("gdsm.services.oauth.load_secret", return_value="old")
    def test_revoked_refresh_grant_requests_sign_in(self, load):
        error = urllib.error.HTTPError(
            "", 400, "Bad Request", {}, io.BytesIO(b'{"error":"invalid_grant"}')
        )
        with (
            patch.object(self.oauth, "_exchange", side_effect=error),
            patch.object(
                self.oauth, "_interactive", return_value="signed-in"
            ) as browser,
        ):
            self.assertEqual(self.oauth.token(), "signed-in")
            browser.assert_called_once()

    def test_short_lived_tokens_are_not_cached_beyond_expiry(self):
        response = Mock()
        response.__enter__ = Mock(
            return_value=io.BytesIO(b'{"access_token":"short","expires_in":10}')
        )
        response.__exit__ = Mock(return_value=False)
        with (
            patch("gdsm.services.oauth.urllib.request.urlopen", return_value=response),
            patch("gdsm.services.oauth.time.time", return_value=100),
        ):
            self.oauth._exchange({})
        self.assertEqual(self.oauth.expiry, 109)

    def test_invalid_token_payload_does_not_publish_state(self):
        for payload in (
            [],
            {},
            {"access_token": ""},
            {"access_token": "x", "expires_in": -1},
        ):
            with self.subTest(payload=payload):
                response = Mock()
                response.__enter__ = Mock(
                    return_value=io.BytesIO(json.dumps(payload).encode())
                )
                response.__exit__ = Mock(return_value=False)
                with (
                    patch(
                        "gdsm.services.oauth.urllib.request.urlopen",
                        return_value=response,
                    ),
                    self.assertRaises(ValueError),
                ):
                    self.oauth._exchange({})
                self.assertEqual(self.oauth.access, "")

    def test_callback_ignores_invalid_state_and_accepts_valid_callback(self):
        server = OAuthCallbackServer(("127.0.0.1", 0), OAuthCallbackHandler, "expected")
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/"
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(url + "?state=wrong&code=unused", timeout=2)
            caught.exception.close()
            self.assertFalse(server.oauth_ready.is_set())
            with urllib.request.urlopen(
                url + "?state=expected&code=accepted", timeout=2
            ) as response:
                self.assertEqual(response.status, 200)
            self.assertTrue(server.oauth_ready.wait(2))
            self.assertEqual(server.oauth_result["code"], "accepted")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
