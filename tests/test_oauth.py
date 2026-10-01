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
    def test_thread_safe_token_refresh(self, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        mock_load_secret.return_value = "dummy_refresh_token"

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # We'll use threading primitives to contest the lock deterministically
        import threading

        started = threading.Event()
        proceed = threading.Event()
        exchange_calls = []

        def mock_exchange(data):
            # Record that exchange was called
            exchange_calls.append(data)
            # Signal that the first thread is inside _exchange
            started.set()
            # Wait until other threads have queued up
            proceed.wait()
            # Simulate real exchange side effects
            oauth.access = "new_access_token"
            oauth.expiry = 9999999999
            return "new_access_token"

        oauth._exchange = mock_exchange

        def run_token(results_list, index):
            results_list[index] = oauth.token()

        results = [None, None, None]

        t1 = threading.Thread(target=run_token, args=(results, 0))
        t2 = threading.Thread(target=run_token, args=(results, 1))
        t3 = threading.Thread(target=run_token, args=(results, 2))

        # Start thread 1, which will acquire _refresh_lock and block in mock_exchange
        t1.start()

        # Wait until t1 is inside _exchange
        started.wait()

        # Start t2 and t3, they will block waiting for _refresh_lock
        t2.start()
        t3.start()

        import time
        time.sleep(0.1)  # Ensure t2 and t3 are actually blocked on the lock

        # Let t1 finish
        proceed.set()

        t1.join()
        t2.join()
        t3.join()

        # All threads should get the same new token
        self.assertEqual(results, ["new_access_token", "new_access_token", "new_access_token"])

        # _exchange should only be called once due to double-checked locking
        self.assertEqual(len(exchange_calls), 1)

if __name__ == "__main__":
    unittest.main()
