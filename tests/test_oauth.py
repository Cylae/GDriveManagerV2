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

        import time
        import threading

        exchange_calls = 0
        def fake_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            time.sleep(0.1) # Simulate slow network
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return "new_access_token"

        with patch.object(oauth, "_exchange", side_effect=fake_exchange):
            def worker():
                oauth.token()

            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(exchange_calls, 1)
        self.assertEqual(oauth.access, "new_access_token")

if __name__ == "__main__":
    unittest.main()
