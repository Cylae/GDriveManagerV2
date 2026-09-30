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
    @patch.object(GoogleOAuth, "_exchange")
    def test_concurrent_refresh_locking(self, mock_exchange, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)
        mock_load_secret.return_value = "dummy_refresh_token"

        import threading
        import time

        started = threading.Event()
        proceed = threading.Event()

        def slow_exchange(data):
            started.set()
            proceed.wait()
            # simulate side-effects
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
            return "new_token"

        mock_exchange.side_effect = slow_exchange

        def fetch():
            return oauth.token()

        t1 = threading.Thread(target=fetch)
        t2 = threading.Thread(target=fetch)

        t1.start()
        started.wait() # Wait for t1 to enter slow_exchange

        t2.start() # t2 will block on refresh_lock because t1 holds it

        # let t1 finish
        proceed.set()

        t1.join()
        t2.join()

        # _exchange should be called only once, because t2 will do a double-check
        # when it gets the _refresh_lock and find the token is valid
        mock_exchange.assert_called_once()
        self.assertEqual(oauth.access, "new_token")


if __name__ == "__main__":
    unittest.main()
