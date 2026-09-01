import unittest
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


class OAuthTests(unittest.TestCase):
    @patch("gdsm.services.oauth.load_secret")
    def test_token_refresh_thread_safety(self, mock_load_secret):
        import time
        import threading

        mock_load_secret.return_value = "dummy_refresh_token"

        settings = Settings(client_id="test_client_id")
        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        call_count = [0]

        def fake_exchange(data):
            # Simulate network delay during refresh
            time.sleep(0.1)
            call_count[0] += 1
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return oauth.access

        # Patch the _exchange method directly
        with patch.object(oauth, '_exchange', side_effect=fake_exchange):
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

            self.assertEqual(call_count[0], 1, "_exchange should only be called once")
            self.assertEqual(len(results), 5)
            for res in results:
                self.assertEqual(res, "new_access_token")

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
