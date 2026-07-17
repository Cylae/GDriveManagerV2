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
    def test_token_concurrent_refresh(self, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        mock_load_secret.return_value = "fake_refresh_token"

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        exchange_calls = 0
        def side_effect_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            oauth.access = "new_access_token"
            import time
            oauth.expiry = time.time() + 3600
            # simulate network delay to increase probability of race condition if lock fails
            time.sleep(0.05)
            return oauth.access

        with patch.object(oauth, "_exchange", side_effect=side_effect_exchange):
            import threading

            def get_token():
                oauth.token()

            threads = [threading.Thread(target=get_token) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(exchange_calls, 1)
            self.assertEqual(oauth.access, "new_access_token")

if __name__ == "__main__":
    unittest.main()
