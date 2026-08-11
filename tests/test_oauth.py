import unittest
from unittest.mock import patch
import concurrent.futures
import time
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


class OAuthTests(unittest.TestCase):
    @patch("gdsm.services.oauth.load_secret")
    def test_token_concurrent_refresh(self, mock_load):
        """Test that concurrent calls to token() only trigger one refresh operation."""
        mock_load.return_value = "fake_refresh_token"
        settings = Settings(client_id="test_client_id")

        oauth = GoogleOAuth(settings, lambda x: None)

        call_count = 0
        def mock_exchange(data):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1) # Simulate network delay
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
            return "new_token"

        oauth._exchange = mock_exchange

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(oauth.token) for _ in range(5)]
            results = [f.result() for f in futures]

        self.assertEqual(results, ["new_token"] * 5)
        self.assertEqual(call_count, 1)

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

if __name__ == "__main__":
    unittest.main()
