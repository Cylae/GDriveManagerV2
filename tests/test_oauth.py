import threading
import time
import unittest
from unittest.mock import patch, MagicMock
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
    def test_token_double_checked_locking(self, mock_load_secret):
        mock_load_secret.return_value = "fake_refresh_token"
        settings = Settings(client_id="test_client")
        oauth = GoogleOAuth(settings, lambda s: None)

        exchange_calls = 0
        def fake_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            time.sleep(0.1) # Simulate network delay
            with oauth._lock:
                oauth.access = "new_access"
                oauth.expiry = time.time() + 3600
            return "new_access"

        oauth._exchange = MagicMock(side_effect=fake_exchange)

        def call_token():
            oauth.token()

        threads = [threading.Thread(target=call_token) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one thread should actually perform the exchange because of double-checked locking
        self.assertEqual(exchange_calls, 1)
        self.assertEqual(oauth.access, "new_access")

    def test_logout_does_not_block_on_refresh(self):
        settings = Settings(client_id="test_client")
        oauth = GoogleOAuth(settings, lambda s: None)
        oauth.access = "old_access"
        oauth.expiry = time.time() + 3600

        # Simulate a refresh in progress holding the refresh lock
        oauth._refresh_lock.acquire()

        # We can still logout because it only needs the inner _lock
        oauth.logout()

        self.assertEqual(oauth.access, "")
        self.assertEqual(oauth.expiry, 0)

        oauth._refresh_lock.release()

if __name__ == "__main__":
    unittest.main()
