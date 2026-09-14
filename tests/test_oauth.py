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
    def test_token_refresh_thread_safety(self, mock_load_secret):
        """Test that concurrent refresh requests are safely serialized."""
        import threading
        import time

        mock_load_secret.return_value = "fake_refresh_token"
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        exchange_started = threading.Event()
        resume_exchange = threading.Event()
        exchange_called = [0]

        def mock_exchange(data):
            exchange_called[0] += 1
            exchange_started.set()
            resume_exchange.wait(timeout=5)  # Wait for main thread to signal

            # Simulate real _exchange side effects while holding _lock implicitly
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
                access = oauth.access
            return access

        with patch.object(oauth, "_exchange", side_effect=mock_exchange):
            def thread_func():
                return oauth.token()

            # Thread 1 starts the token refresh
            t1 = threading.Thread(target=thread_func)
            t1.start()

            # Wait for Thread 1 to enter _exchange
            exchange_started.wait(timeout=5)

            # Thread 2 tries to get a token concurrently
            results = {}
            def thread2_func():
                results["t2"] = oauth.token()

            t2 = threading.Thread(target=thread2_func)
            t2.start()

            # Give T2 a moment to block on _refresh_lock
            time.sleep(0.1)

            # Allow T1 to finish its exchange
            resume_exchange.set()

            t1.join(timeout=5)
            t2.join(timeout=5)

            # Both threads should get the same new access token
            self.assertEqual(oauth.access, "new_access_token")
            self.assertEqual(results.get("t2"), "new_access_token")

            # _exchange should only have been called ONCE due to double-checked locking
            self.assertEqual(exchange_called[0], 1)


if __name__ == "__main__":
    unittest.main()
