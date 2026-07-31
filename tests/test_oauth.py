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
    def test_token_refresh_thread_safety(self, mock_exchange, mock_load_secret):
        import time
        import threading

        mock_load_secret.return_value = "dummy_refresh_token"

        def side_effect(data):
            time.sleep(0.1)  # Simulate network delay to encourage race condition
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return oauth.access

        mock_exchange.side_effect = side_effect

        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        threads = []
        results = []
        exceptions = []

        def call_token():
            try:
                results.append(oauth.token())
            except Exception as e:
                exceptions.append(e)

        for _ in range(5):
            t = threading.Thread(target=call_token)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(exceptions), 0)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "new_access_token" for r in results))
        mock_exchange.assert_called_once()

if __name__ == "__main__":
    unittest.main()
