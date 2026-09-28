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

    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.time")
    def test_token_thread_safety(self, mock_time, mock_load_secret):
        mock_load_secret.return_value = "refresh123"
        mock_time.time.return_value = 100
        settings = Settings(client_id="client1")
        oauth = GoogleOAuth(settings, lambda s: None)

        calls = 0

        def fake_exchange(data):
            nonlocal calls
            calls += 1
            time.sleep(0.1) # Simulate slow network
            with oauth._lock:
                oauth.access = f"tok{calls}"
                oauth.expiry = 200
            return f"tok{calls}"

        oauth._exchange = fake_exchange

        threads = []
        results = []
        def worker():
            results.append(oauth.token())

        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(calls, 1, "Exchange should only be called once due to double-checked locking")
        self.assertEqual(results, ["tok1", "tok1", "tok1", "tok1", "tok1"])

    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.delete_secret")
    def test_logout_waits_for_refresh(self, mock_delete_secret, mock_load_secret):
        mock_load_secret.return_value = "ref"
        settings = Settings(client_id="client")
        oauth = GoogleOAuth(settings, lambda s: None)

        event = threading.Event()

        def fake_exchange(data):
            event.set()
            time.sleep(0.2)
            with oauth._lock:
                oauth.access = "stale_token"
                oauth.expiry = time.time() + 3600
            return "stale_token"

        oauth._exchange = fake_exchange

        t = threading.Thread(target=oauth.token)
        t.start()

        event.wait()
        oauth.logout()
        t.join()

        self.assertEqual(oauth.access, "", "Logout must clear access token even if refresh completes just before")
        self.assertEqual(oauth.expiry, 0)
        mock_delete_secret.assert_called_once()

if __name__ == "__main__":
    unittest.main()
