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

    def test_token_double_checked_locking(self):
        import threading
        import time
        from unittest.mock import MagicMock

        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        # We need a mock for _exchange that will block for a moment to simulate network,
        # then set the token and expiry correctly.
        call_count = 0
        def mock_exchange(data):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1) # Simulate network delay
            with oauth._lock:
                oauth.access = f"token_{call_count}"
                oauth.expiry = time.time() + 3600
            return oauth.access

        oauth._exchange = MagicMock(side_effect=mock_exchange)

        # Mock load_secret to simulate we have a refresh token
        with patch("gdsm.services.oauth.load_secret", return_value="some_refresh_token"):
            def worker():
                return oauth.token()

            threads = []
            results = []

            def run_worker():
                results.append(worker())

            for _ in range(5):
                t = threading.Thread(target=run_worker)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # The key is that _exchange should only be called ONCE because of the double-checked locking,
            # even though 5 threads tried to get the token concurrently.
            self.assertEqual(call_count, 1)
            # All threads should get the exact same token
            self.assertEqual(results, ["token_1"] * 5)
            self.assertEqual(oauth.access, "token_1")


if __name__ == "__main__":
    unittest.main()
