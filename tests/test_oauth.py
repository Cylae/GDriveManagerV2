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
    @patch.object(GoogleOAuth, "_exchange")
    def test_token_refresh_thread_safety(self, mock_exchange, mock_load_secret):
        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        mock_load_secret.return_value = "dummy_refresh_token"

        def slow_exchange(data):
            import time
            time.sleep(0.1)
            # Ensure mock explicitly sets oauth.access and oauth.expiry
            # to simulate the real method's side effects as per memory instructions
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return "new_access_token"

        mock_exchange.side_effect = slow_exchange

        oauth = GoogleOAuth(settings, mock_on_refresh)

        import threading
        threads = []
        results = []

        def worker():
            res = oauth.token()
            results.append(res)

        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r, "new_access_token")

        # _exchange should only be called once due to double-checked locking
        mock_exchange.assert_called_once()


if __name__ == "__main__":
    unittest.main()
