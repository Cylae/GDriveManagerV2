import time
import threading
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
    def test_concurrent_token_refresh(self, mock_load_secret):
        mock_load_secret.return_value = "dummy_refresh_token"
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        call_count = [0]

        def mock_exchange(data):
            call_count[0] += 1
            time.sleep(0.1)  # Simulate network delay
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return "new_access_token"

        with patch.object(oauth, "_exchange", side_effect=mock_exchange):
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

        self.assertEqual(call_count[0], 1, "Exchange should only be called once")
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r, "new_access_token")

    @patch("gdsm.services.oauth.delete_secret")
    def test_logout_does_not_block_on_refresh(self, mock_delete_secret):
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)
        oauth.access = "old_token"
        oauth.expiry = time.time() + 3600

        # Simulate a network refresh operation holding the lock
        oauth._refresh_lock.acquire()

        try:
            start = time.time()
            oauth.logout()
            end = time.time()

            # Should be nearly instant because logout only needs _lock, not _refresh_lock
            self.assertLess(end - start, 0.1)
            self.assertEqual(oauth.access, "")
            self.assertEqual(oauth.expiry, 0)
        finally:
            oauth._refresh_lock.release()

if __name__ == "__main__":
    unittest.main()
