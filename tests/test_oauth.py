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
        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # Make load_secret return a dummy refresh token
        mock_load_secret.return_value = "dummy_refresh_token"

        # We need to mock _exchange to track how many times it's called
        exchange_calls = 0

        def mock_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            # Simulate side effects of _exchange
            import time
            with oauth._lock:
                oauth.access = f"new_token_{exchange_calls}"
                oauth.expiry = time.time() + 3600

            # Simulate a slow network call so threads overlap
            time.sleep(0.1)

            return oauth.access

        oauth._exchange = mock_exchange

        import threading

        # Create multiple threads that will request a token concurrently
        results = []
        threads = []

        def worker():
            results.append(oauth.token())

        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify that _exchange was only called exactly once
        self.assertEqual(exchange_calls, 1)

        # Verify all threads got the same resulting token
        for result in results:
            self.assertEqual(result, "new_token_1")

if __name__ == "__main__":
    unittest.main()
