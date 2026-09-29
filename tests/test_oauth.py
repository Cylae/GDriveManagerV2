import unittest
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth


import time
import threading

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
        mock_load_secret.return_value = "fake_refresh_token"
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        call_count = 0

        def mock_exchange(data):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1) # Simulate network delay
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
            return "new_token"

        oauth._exchange = mock_exchange

        def worker(results, index):
            results[index] = oauth.token()

        threads = []
        results = [None] * 5
        for i in range(5):
            t = threading.Thread(target=worker, args=(results, i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All threads should get the same token, and exchange should only be called once
        self.assertEqual(results, ["new_token"] * 5)
        self.assertEqual(call_count, 1)

    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.delete_secret")
    def test_logout_thread_safety(self, mock_delete_secret, mock_load_secret):
        mock_load_secret.return_value = "fake_refresh_token"
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        # We need to simulate a case where a refresh is in progress, and logout is called

        # Mock exchange to block until we tell it to proceed
        exchange_started = threading.Event()
        exchange_proceed = threading.Event()

        def mock_exchange(data):
            exchange_started.set()
            exchange_proceed.wait()
            with oauth._lock:
                oauth.access = "new_token"
                oauth.expiry = time.time() + 3600
            return "new_token"

        oauth._exchange = mock_exchange

        # Start refresh in background
        t = threading.Thread(target=oauth.token)
        t.start()

        # Wait for exchange to start (it has acquired refresh_lock)
        exchange_started.wait()

        # Now try to logout. This should block because refresh_lock is held.
        logout_thread = threading.Thread(target=oauth.logout)
        logout_thread.start()

        # Let exchange finish
        exchange_proceed.set()

        # Wait for both to finish
        t.join()
        logout_thread.join()

        # After logout, state should be cleared, even if refresh finished just before logout
        self.assertEqual(oauth.access, "")
        self.assertEqual(oauth.expiry, 0)

if __name__ == "__main__":
    unittest.main()
