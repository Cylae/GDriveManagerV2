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
    def test_thread_safe_token_refresh(self, mock_load_secret):
        from concurrent.futures import ThreadPoolExecutor
        import time

        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)
        mock_load_secret.return_value = "fake_refresh_token"

        exchange_calls = 0

        def mock_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            # simulate network latency
            time.sleep(0.05)
            # simulate what real _exchange does
            oauth.access = "new_token"
            oauth.expiry = time.time() + 3600
            return oauth.access

        with patch.object(oauth, "_exchange", side_effect=mock_exchange):
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(oauth.token) for _ in range(5)]
                results = [f.result() for f in futures]

        self.assertEqual(exchange_calls, 1)
        self.assertEqual(results, ["new_token"] * 5)
        self.assertEqual(oauth.access, "new_token")

if __name__ == "__main__":
    unittest.main()
