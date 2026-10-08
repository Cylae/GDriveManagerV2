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

    @patch("gdsm.services.oauth.GoogleOAuth._exchange")
    @patch("gdsm.services.oauth.load_secret")
    def test_concurrent_refresh(self, mock_load, mock_exchange):
        import threading
        import time
        mock_load.return_value = "refresh"
        settings = Settings(client_id="test")
        oauth = GoogleOAuth(settings, lambda s: None)

        ready = threading.Event()
        proceed = threading.Event()

        def mock_exchange_side_effect(data):
            ready.set()
            proceed.wait()
            with oauth._lock:
                oauth.access = "new"
                oauth.expiry = time.time() + 3600
            return "new"

        mock_exchange.side_effect = mock_exchange_side_effect

        results = []
        def worker():
            results.append(oauth.token())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()
        t2.start()

        ready.wait()
        proceed.set()

        t1.join()
        t2.join()

        mock_exchange.assert_called_once()
        self.assertEqual(results, ["new", "new"])

if __name__ == "__main__":
    unittest.main()
