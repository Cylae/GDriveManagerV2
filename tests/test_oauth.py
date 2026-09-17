import threading
import time
import unittest
from unittest.mock import MagicMock, patch

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
        settings = Settings(client_id="test_client_id")
        mock_load_secret.return_value = "fake_refresh_token"

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # We'll mock _exchange to have a small sleep to simulate network
        # and ensure other threads wait. It sets access and expiry correctly.
        call_count = 0
        def fake_exchange(data):
            nonlocal call_count
            time.sleep(0.1) # Simulate network delay
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
                call_count += 1
            return oauth.access

        oauth._exchange = MagicMock(side_effect=fake_exchange)

        def fetch_token(results_list, index):
            try:
                t = oauth.token()
                results_list[index] = t
            except Exception as e:
                results_list[index] = e

        num_threads = 5
        threads = []
        results = [None] * num_threads

        for i in range(num_threads):
            t = threading.Thread(target=fetch_token, args=(results, i))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify that all threads got the correct token
        for res in results:
            self.assertEqual(res, "new_token")

        # Verify _exchange was only called once despite 5 threads attempting it
        self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
