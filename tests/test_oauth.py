import unittest
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


import threading
import time
from unittest.mock import MagicMock

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
        mock_load_secret.return_value = "fake_refresh_token"

        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        call_count = 0

        def mock_exchange_behavior(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1) # Simulate network delay
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
                access = oauth.access
            return access

        oauth._exchange = MagicMock(side_effect=mock_exchange_behavior) # type: ignore

        results = []
        def fetch():
            results.append(oauth.token())

        threads = []
        for _ in range(5):
            t = threading.Thread(target=fetch)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(call_count, 1, "Exchange should only be called once due to locking")
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == "new_token" for r in results))


if __name__ == "__main__":
    unittest.main()
