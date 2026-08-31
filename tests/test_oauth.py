import unittest
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


import threading
import time

class OAuthTests(unittest.TestCase):
    @patch("gdsm.services.oauth.load_secret")
    def test_token_thread_safety(self, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        def mock_on_refresh(s): pass
        oauth = GoogleOAuth(settings, mock_on_refresh)

        mock_load_secret.return_value = "fake_refresh_token"

        exchange_calls = 0
        def fake_exchange(data):
            nonlocal exchange_calls
            # Simulate a slow network call
            time.sleep(0.1)
            exchange_calls += 1
            # Mock the side effects of _exchange as per memory constraints
            with oauth._lock:
                oauth.access = f"token_{exchange_calls}"
                oauth.expiry = time.time() + 3600
            return oauth.access

        # Patch the _exchange method specifically for this test instance
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

        # Ensure that only one network call was made (exchange_calls == 1)
        # despite 5 threads requesting the token concurrently
        self.assertEqual(exchange_calls, 1)

        # All threads should have received the exact same token
        for res in results:
            self.assertEqual(res, "token_1")

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
