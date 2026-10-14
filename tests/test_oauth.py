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
    @patch("gdsm.services.oauth.delete_secret")
    def test_thread_safety_refresh_and_logout(self, mock_delete_secret, mock_load_secret):
        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        import threading

        refresh_started = threading.Event()
        refresh_proceed = threading.Event()

        # We need to mock _exchange such that we can control its execution
        # to guarantee the first thread holds the `_refresh_lock` while
        # the second thread waits for it.

        def blocking_exchange(data):
            refresh_started.set()
            refresh_proceed.wait()
            # Fake the real exchange side-effect
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = 1234567890
            return "new_token"

        oauth._exchange = blocking_exchange
        mock_load_secret.return_value = "fake_refresh_token"

        def fetch_token():
            return oauth.token()

        t1 = threading.Thread(target=fetch_token)
        t1.start()

        # Wait for t1 to start the exchange and hold _refresh_lock
        refresh_started.wait(timeout=2.0)
        self.assertTrue(refresh_started.is_set(), "Thread 1 did not reach exchange")

        # Now t1 holds _refresh_lock.
        # t2 should block waiting for it.
        results = []
        def fetch_token_2():
            res = oauth.token()
            results.append(res)

        t2 = threading.Thread(target=fetch_token_2)
        t2.start()

        # Give t2 a moment to get blocked
        import time
        time.sleep(0.1)

        # While t1 is doing the exchange, logout should STILL work without blocking
        oauth.logout()
        # Verify the state was cleared
        with oauth._lock:
            self.assertEqual(oauth.access, "")
            self.assertEqual(oauth.expiry, 0)

        # Let t1 finish the exchange
        refresh_proceed.set()

        t1.join(timeout=2.0)
        t2.join(timeout=2.0)

        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        # t2 should get the new token, and it shouldn't trigger a second exchange
        # because of double checked locking (even if our blocking exchange mock isn't counting calls,
        # t2 checking access/expiry inside _refresh_lock would return "new_token"
        # Since logout happened concurrently, t2 might actually fetch again or get the cached one depending on timing,
        # but in our test `_exchange` directly set the token and t2 fetches after that.
        # Actually since we cleared it with logout() concurrently, let's just make sure both threads complete without deadlock.

        # Verify logout deleted the secret
        mock_delete_secret.assert_called()


if __name__ == "__main__":
    unittest.main()
