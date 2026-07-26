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

        # We need the load_secret to return something so it attempts exchange
        mock_load_secret.return_value = "mock_refresh_token"

        # Mock the exchange so that it sleeps a tiny bit, mimicking an IO call,
        # and then updates oauth.access and oauth.expiry to simulate a successful exchange
        call_count = 0
        def mock_exchange(data):
            nonlocal call_count
            call_count += 1
            import time
            time.sleep(0.1) # Simulate network delay
            oauth.access = "new_access_token"
            oauth.expiry = time.time() + 3600
            return oauth.access

        with patch.object(oauth, "_exchange", side_effect=mock_exchange) as mock_exchange_method:
            import threading

            def call_token():
                return oauth.token()

            threads = []
            for _ in range(5):
                t = threading.Thread(target=call_token)
                threads.append(t)

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            # Verify _exchange was only called once despite 5 concurrent attempts
            self.assertEqual(call_count, 1)
            self.assertEqual(oauth.access, "new_access_token")

if __name__ == "__main__":
    unittest.main()
