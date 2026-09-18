import unittest
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


class OAuthTests(unittest.TestCase):
    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.delete_secret")
    def test_token_refresh_thread_safety(self, mock_delete_secret, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        mock_load_secret.return_value = "fake_refresh_token"

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        import threading
        import time
        from unittest.mock import MagicMock

        # Track number of calls to _exchange
        call_count = 0
        call_lock = threading.Lock()

        # Custom mock for _exchange that simulates a slow network request
        # and correctly sets the state lock variables as requested in memory rules.
        def slow_exchange(data):
            nonlocal call_count
            with call_lock:
                call_count += 1
            time.sleep(0.1) # Simulate slow network

            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
                return oauth.access

        oauth._exchange = MagicMock(side_effect=slow_exchange)

        # Launch multiple threads simultaneously requesting a token
        results = []
        threads = []
        for _ in range(5):
            t = threading.Thread(target=lambda: results.append(oauth.token()))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Ensure all threads got the correct new token
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "new_token" for r in results))

        # Crucially, ensure the actual network exchange was only called ONCE
        # despite 5 threads attempting to get a token simultaneously while it was empty.
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
