import unittest
from unittest.mock import patch

from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


class OAuthTests(unittest.TestCase):
    @patch("gdsm.services.oauth.delete_secret")
    def test_logout_resets_state_and_deletes_secret(self, mock_delete_secret):
        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)
        oauth.access = "test_access_token"
        oauth.expiry = 1234567890

        # Verify setup
        self.assertEqual(oauth.access, "test_access_token")
        self.assertEqual(oauth.expiry, 1234567890)

        # Call logout
        oauth.logout()

        # Verify logout
        self.assertEqual(oauth.access, "")
        self.assertEqual(oauth.expiry, 0)

        # Verify secret deletion
        mock_delete_secret.assert_called_once_with("refresh_token")

    @patch("gdsm.services.oauth.load_secret")
    def test_concurrent_token_refresh(self, mock_load_secret):
        import threading
        import time

        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # Simulate existing refresh token
        mock_load_secret.return_value = "fake_refresh_token"

        started = threading.Event()
        proceed = threading.Event()
        exchange_calls = 0

        # Replace _exchange with a method that blocks to simulate slow network
        def fake_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            started.set()
            proceed.wait()
            # Must explicitly set oauth.access and oauth.expiry to simulate side effects of real _exchange
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return "new_access_token"

        oauth._exchange = fake_exchange

        results = []

        def worker():
            try:
                res = oauth.token()
                results.append(res)
            except Exception as e:  # noqa: BLE001
                results.append(e)

        # Start first thread that will block in _exchange
        t1 = threading.Thread(target=worker)
        t1.start()

        started.wait(timeout=5.0)

        # Start second thread that should wait on _refresh_lock
        t2 = threading.Thread(target=worker)
        t2.start()

        # Give t2 a moment to block
        time.sleep(0.1)

        # Prove logout doesn't freeze the UI (only needs _lock)
        # However we need to be careful: if logout runs, it clears token.
        # So we just test calling logout doesn't block.
        # Actually wait, logout clears state, so t2 might fetch a new one? No, t2 is blocked on _refresh_lock.
        # Let's let the threads finish first to avoid race in test logic.

        # Unblock t1
        proceed.set()

        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "new_access_token")
        self.assertEqual(results[1], "new_access_token")
        self.assertEqual(exchange_calls, 1)  # Prove double-checked locking works

        # Verify logout doesn't block and clears state
        oauth.logout()
        self.assertEqual(oauth.access, "")
        self.assertEqual(oauth.expiry, 0)


if __name__ == "__main__":
    unittest.main()
