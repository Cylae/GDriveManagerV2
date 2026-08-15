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
    def test_concurrent_token_refresh(self, mock_exchange, mock_load_secret):
        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        mock_load_secret.return_value = "fake_refresh_token"

        # When _exchange is called, it should set the access token and expiry
        # to simulate the real _exchange method since the double checked lock relies on it
        def side_effect(data):
            import time
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return oauth.access

        mock_exchange.side_effect = side_effect

        oauth = GoogleOAuth(settings, mock_on_refresh)

        import threading

        results = []
        def worker():
            results.append(oauth.token())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 10)
        self.assertTrue(all(r == "new_access_token" for r in results))
        mock_exchange.assert_called_once()
        mock_load_secret.assert_called_once_with("refresh_token")

if __name__ == "__main__":
    unittest.main()
