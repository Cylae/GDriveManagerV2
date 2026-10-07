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
        mock_load_secret.return_value = "fake_refresh_token"

        import threading

        # We'll use threading events to coordinate the threads so the second thread
        # definitely hits the first lock, waits for the refresh_lock, and then
        # gets the already-refreshed token without making a second network request.

        started = threading.Event()
        proceed = threading.Event()

        exchange_calls = 0

        def fake_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            # Signal that the first thread is inside the refresh block
            started.set()
            # Wait for the main thread to let us finish
            proceed.wait()

            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = 2000000000
            return "new_token"

        oauth._exchange = fake_exchange

        results = []
        def worker():
            results.append(oauth.token())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)

        t1.start()

        # Wait until t1 is inside _exchange and holding the _refresh_lock
        started.wait()

        # Start t2, which should block waiting for _refresh_lock, or get the
        # already-updated token if t1 finishes.
        t2.start()

        # Let t1 finish the exchange
        proceed.set()

        t1.join()
        t2.join()

        self.assertEqual(results, ["new_token", "new_token"])
        self.assertEqual(exchange_calls, 1)

if __name__ == "__main__":
    unittest.main()
