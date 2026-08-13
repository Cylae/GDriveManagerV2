import unittest
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


class OAuthTests(unittest.TestCase):
    @patch("gdsm.services.oauth.load_secret")
    def test_concurrent_token_refresh(self, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # Simulate an expired token that triggers a refresh
        oauth.access = "expired_token"
        oauth.expiry = 0

        # Return a dummy refresh token to trigger _exchange instead of _interactive
        mock_load_secret.return_value = "dummy_refresh_token"

        with patch.object(oauth, "_exchange") as mock_exchange:
            # We must simulate what the real _exchange does under lock,
            # otherwise the second thread will still think it needs to refresh
            def mock_exchange_side_effect(data):
                import time
                # Simulate network delay to encourage race conditions
                time.sleep(0.05)
                with oauth._lock:
                    oauth.access = "new_access_token"
                    oauth.expiry = time.time() + 3600
                return oauth.access

            mock_exchange.side_effect = mock_exchange_side_effect

            import threading

            results = []
            threads = []

            def worker():
                try:
                    res = oauth.token()
                    results.append(res)
                except Exception as e:
                    results.append(e)

            # Start multiple threads concurrently
            for _ in range(5):
                t = threading.Thread(target=worker)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Ensure all workers got the new token
            for res in results:
                self.assertEqual(res, "new_access_token")

            # Ensure the actual network exchange only happened exactly once
            mock_exchange.assert_called_once()


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
