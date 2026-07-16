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
    def test_token_refresh_is_thread_safe(self, mock_load_secret):
        mock_load_secret.return_value = "fake_refresh_token"
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        call_count = 0
        def mock_exchange(data):
            nonlocal call_count
            import time
            time.sleep(0.1)  # Simulate network latency to encourage race conditions
            call_count += 1
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return oauth.access

        # Patch the instance method directly
        oauth._exchange = mock_exchange

        import threading

        def worker():
            oauth.token()

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # If thread-safe, _exchange should only be called once, because
        # the first thread will hold the lock, sleep, update the token, release the lock.
        # The 9 other threads will then acquire the lock, see that the token is now valid
        # via double-checked locking, and return without calling _exchange again.
        self.assertEqual(call_count, 1)

if __name__ == "__main__":
    unittest.main()
