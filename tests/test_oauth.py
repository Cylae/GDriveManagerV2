import unittest
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


import threading
import time

class OAuthTests(unittest.TestCase):
    @patch("gdsm.services.oauth.load_secret")
    def test_token_thread_safety(self, mock_load_secret):
        # Setup settings and mock on_refresh
        settings = Settings(client_id="test_client_id")
        def mock_on_refresh(s):
            pass

        # Mock load_secret to simulate a stored refresh token
        mock_load_secret.return_value = "dummy_refresh_token"

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # We mock _exchange to simulate a network delay
        call_count = [0]

        def mocked_exchange(data):
            time.sleep(0.1)  # Simulate network delay
            call_count[0] += 1
            with oauth._lock:
                oauth.access = "mocked_access_token"
                oauth.expiry = time.time() + 3600
            return oauth.access

        oauth._exchange = mocked_exchange

        # Spawn multiple threads calling token()
        threads = []
        results = []
        def worker():
            results.append(oauth.token())

        for _ in range(5):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # Check results
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "mocked_access_token" for r in results))

        # Verify that _exchange was only called once, thanks to double-checked locking
        self.assertEqual(call_count[0], 1)

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
