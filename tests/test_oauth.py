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
        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # Simulate that a refresh token is present
        mock_load_secret.return_value = "dummy_refresh_token"

        # Mock _exchange to simulate a slight network delay and then update state
        import time
        import threading

        call_count = 0
        def fake_exchange(data):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1) # Simulate delay
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return oauth.access

        # We must use patch.object on the instance, or directly assign to oauth._exchange
        with patch.object(oauth, "_exchange", side_effect=fake_exchange) as mock_exchange:
            # We want multiple threads to call token() concurrently
            threads = []
            results = []

            def thread_target():
                try:
                    res = oauth.token()
                    results.append(res)
                except Exception as e:
                    results.append(e)

            for _ in range(5):
                t = threading.Thread(target=thread_target)
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # The token method should have returned the new access token for all threads
            for r in results:
                self.assertEqual(r, "new_access_token")

            # But _exchange should have only been called once due to double-checked locking
            self.assertEqual(call_count, 1)

if __name__ == "__main__":
    unittest.main()
