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
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        mock_load_secret.return_value = "fake_refresh_token"

        call_count = 0
        import time
        import threading

        def fake_exchange(data):
            nonlocal call_count
            call_count += 1
            # Simulate a slow network call
            time.sleep(0.5)
            # Update state exactly as real _exchange does
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return oauth.access

        # Stub _exchange with our fake method
        oauth._exchange = fake_exchange

        results = []
        def worker():
            results.append(oauth.token())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same token and _exchange should only be called once
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r, "new_access_token")
        self.assertEqual(call_count, 1)

if __name__ == "__main__":
    unittest.main()
