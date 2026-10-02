import threading
import time
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

    @patch("gdsm.services.oauth.delete_secret")
    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.GoogleOAuth._exchange")
    def test_concurrent_refresh(self, mock_exchange, mock_load_secret, mock_delete_secret):
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        mock_load_secret.return_value = "fake_refresh_token"

        started = threading.Event()
        proceed = threading.Event()

        def fake_exchange(data):
            started.set()
            proceed.wait()
            # Simulate setting the access token safely to test lock release logic
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
            return "new_token"

        mock_exchange.side_effect = fake_exchange

        results = []
        def worker():
            results.append(oauth.token())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()
        started.wait() # t1 is inside _exchange
        t2.start()
        time.sleep(0.1) # Ensure t2 is blocked on _refresh_lock

        proceed.set() # Let t1 finish

        t1.join()
        t2.join()

        self.assertEqual(results, ["new_token", "new_token"])
        mock_exchange.assert_called_once()

    @patch("gdsm.services.oauth.delete_secret")
    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.GoogleOAuth._exchange")
    def test_logout_during_refresh(self, mock_exchange, mock_load_secret, mock_delete_secret):
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        mock_load_secret.return_value = "fake_refresh_token"

        started = threading.Event()
        proceed = threading.Event()

        def fake_exchange(data):
            started.set()
            proceed.wait()
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
            return "new_token"

        mock_exchange.side_effect = fake_exchange

        t1 = threading.Thread(target=lambda: oauth.token())
        t1.start()

        started.wait() # t1 is inside _exchange

        t2 = threading.Thread(target=oauth.logout)
        t2.start()
        time.sleep(0.1) # Ensure t2 is blocked on _refresh_lock in logout

        proceed.set() # Let t1 finish setting access

        t1.join()
        t2.join()

        with oauth._lock:
            self.assertEqual(oauth.access, "")
            self.assertEqual(oauth.expiry, 0)
        mock_delete_secret.assert_called_once_with("refresh_token")

if __name__ == "__main__":
    unittest.main()
