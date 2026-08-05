import threading
import time
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
    def test_token_concurrency(self, mock_load_secret):
        # Test that _exchange is only called once even if multiple threads request a token simultaneously
        settings = Settings(client_id="test_client_id")

        oauth = GoogleOAuth(settings, lambda s: None)

        mock_load_secret.return_value = "fake_refresh_token"

        with patch.object(oauth, "_exchange") as mock_exchange:
            def mock_exchange_impl(data):
                time.sleep(0.5)
                with oauth._lock:
                    oauth.access = "new_token"
                    oauth.expiry = time.time() + 3600
                return oauth.access

            mock_exchange.side_effect = mock_exchange_impl

            threads = []
            for _ in range(5):
                t = threading.Thread(target=oauth.token)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            mock_exchange.assert_called_once()
            self.assertEqual(oauth.access, "new_token")

if __name__ == "__main__":
    unittest.main()
