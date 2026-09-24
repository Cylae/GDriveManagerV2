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
        mock_load_secret.return_value = "dummy_refresh_token"

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # Mock _exchange to simulate a slow network call that returns a token
        call_count = [0]

        def fake_exchange(data):
            import time
            call_count[0] += 1
            time.sleep(0.1) # Simulate slow call
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
            return "new_token"

        with patch.object(oauth, "_exchange", side_effect=fake_exchange):
            import threading

            results = []
            def fetch_token():
                results.append(oauth.token())

            threads = [threading.Thread(target=fetch_token) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Verify that _exchange was only called once despite 10 concurrent requests
            self.assertEqual(call_count[0], 1)
            # Verify all threads got the same token
            self.assertEqual(len(results), 10)
            self.assertTrue(all(r == "new_token" for r in results))


if __name__ == "__main__":
    unittest.main()
