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
    def test_token_refresh_thread_safety(self, mock_load_secret):
        # Setup settings and mock on_refresh
        from unittest.mock import MagicMock
        settings = Settings(client_id="test_client_id")
        mock_on_refresh = MagicMock()

        # We simulate the token being expired
        oauth = GoogleOAuth(settings, mock_on_refresh)
        oauth.access = "old_token"
        oauth.expiry = 0

        mock_load_secret.return_value = "dummy_refresh_token"

        call_count = 0

        # Replace _exchange to simulate a slow network call
        def fake_exchange(data):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1) # Simulate network delay
            oauth.access = "new_token"
            oauth.expiry = time.time() + 3600
            return oauth.access

        oauth._exchange = fake_exchange

        threads = []
        results = []

        def worker():
            results.append(oauth.token())

        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All threads should have received the new token
        for res in results:
            self.assertEqual(res, "new_token")

        # The actual exchange should only have been called once despite 5 concurrent threads
        self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
