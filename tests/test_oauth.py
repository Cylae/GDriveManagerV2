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
    def test_concurrent_token_refresh(self, mock_exchange, mock_load_secret):
        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        mock_load_secret.return_value = "fake_refresh_token"

        oauth = GoogleOAuth(settings, mock_on_refresh)

        def mock_exchange_impl(data):
            import time
            time.sleep(0.1)
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return "new_access_token"

        mock_exchange.side_effect = mock_exchange_impl

        import threading

        results = []
        def worker():
            results.append(oauth.token())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r, "new_access_token")

        mock_exchange.assert_called_once()

if __name__ == "__main__":
    unittest.main()
