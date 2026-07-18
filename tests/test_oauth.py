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
        import threading
        import time

        settings = Settings(client_id="test_client_id")
        mock_load_secret.return_value = "dummy_refresh_token"

        oauth = GoogleOAuth(settings, lambda s: None)

        # The mock must simulate the real method's side effects
        def side_effect(data):
            # simulate network delay
            time.sleep(0.2)
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return oauth.access

        mock_exchange.side_effect = side_effect

        # Test concurrent token requests
        results = []

        def worker():
            results.append(oauth.token())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "new_access_token" for r in results))

        # _exchange should only be called once due to double-checked locking
        self.assertEqual(mock_exchange.call_count, 1)

if __name__ == "__main__":
    unittest.main()
