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
    @patch("gdsm.services.oauth.GoogleOAuth._exchange")
    def test_token_refresh_is_thread_safe(self, mock_exchange, mock_load_secret):
        import threading
        import time

        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)
        mock_load_secret.return_value = "fake_refresh_token"

        started = threading.Event()
        proceed = threading.Event()

        def mock_exchange_side_effect(data):
            started.set()
            proceed.wait()
            # Must set oauth.access and oauth.expiry to simulate real behavior
            # for double-checked locking to work for the second thread.
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return "new_access_token"

        mock_exchange.side_effect = mock_exchange_side_effect

        results = []
        def worker():
            results.append(oauth.token())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()
        started.wait() # t1 is inside _exchange, holding _refresh_lock
        t2.start() # t2 will block on _refresh_lock in token()

        proceed.set() # let t1 finish
        t1.join()
        t2.join()

        # Verify both threads got the token
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], "new_access_token")
        self.assertEqual(results[1], "new_access_token")

        # Verify _exchange was only called once despite two threads
        mock_exchange.assert_called_once()

if __name__ == "__main__":
    unittest.main()
