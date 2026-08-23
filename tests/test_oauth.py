import threading
import time
import unittest
from unittest.mock import patch, MagicMock
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
        settings = Settings(client_id="test_client_id")
        mock_load_secret.return_value = "refresh_token_value"
        oauth = GoogleOAuth(settings, lambda s: None)

        # Mock _exchange to simulate a slow network call and valid access setting
        def slow_exchange(data):
            time.sleep(0.1)
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return "new_access_token"

        oauth._exchange = MagicMock(side_effect=slow_exchange)

        # Start 5 threads trying to get the token concurrently
        results = []
        threads = []

        def worker():
            results.append(oauth.token())

        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check results
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "new_access_token" for r in results))

        # Ensure _exchange was only called once despite 5 concurrent requests
        oauth._exchange.assert_called_once()


if __name__ == "__main__":
    unittest.main()
