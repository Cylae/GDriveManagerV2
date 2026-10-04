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
    @patch("gdsm.services.oauth.GoogleOAuth._exchange")
    def test_concurrent_refresh(self, mock_exchange, mock_load_secret):
        import threading
        settings = Settings(client_id="test_client_id")

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        mock_load_secret.return_value = "fake_refresh_token"

        start_event = threading.Event()
        proceed_event = threading.Event()

        def side_effect(*args, **kwargs):
            start_event.set()
            proceed_event.wait()
            # Side effect for the exchange, actually changing the token
            oauth.access = "new_token_123"
            oauth.expiry = 9999999999
            return "new_token_123"

        mock_exchange.side_effect = side_effect

        def thread_task(results, index):
            results[index] = oauth.token()

        results = [None, None]

        t1 = threading.Thread(target=thread_task, args=(results, 0))
        t2 = threading.Thread(target=thread_task, args=(results, 1))

        t1.start()

        # Wait for the first thread to enter _exchange and block
        start_event.wait()

        t2.start()

        # Give t2 a tiny bit of time to hit the lock and get blocked
        import time
        time.sleep(0.1)

        proceed_event.set()

        t1.join()
        t2.join()

        # Both threads should get the same token back
        self.assertEqual(results[0], "new_token_123")
        self.assertEqual(results[1], "new_token_123")

        # Crucially, _exchange should only have been called ONCE due to the lock
        self.assertEqual(mock_exchange.call_count, 1)

if __name__ == "__main__":
    unittest.main()
