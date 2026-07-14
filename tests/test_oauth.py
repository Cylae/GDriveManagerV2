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
    def test_concurrent_token_refresh(self, mock_load_secret, mock_exchange):
        mock_load_secret.return_value = "fake_refresh_token"

        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        def slow_exchange(data):
            import time
            time.sleep(0.5)
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return "new_access_token"

        mock_exchange.side_effect = slow_exchange

        import threading
        threads = []
        results = []

        def worker():
            try:
                results.append(oauth.token())
            except Exception as e:
                print(e)

        for _ in range(5):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        mock_exchange.assert_called_once()
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "new_access_token" for r in results))

if __name__ == "__main__":
    unittest.main()
