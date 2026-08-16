import unittest
import threading
import time
from unittest.mock import patch
from gdsm.domain.models import Settings
from gdsm.services.oauth import GoogleOAuth

class OAuthThreadSafeTests(unittest.TestCase):
    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.save_secret")
    def test_token_double_checked_locking(self, mock_save, mock_load):
        mock_load.return_value = "refresh123"
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        # We want to mock _exchange and see how many times it's called
        exchange_calls = 0
        def mock_exchange(data):
            nonlocal exchange_calls
            exchange_calls += 1
            # Simulate network delay
            time.sleep(0.2)
            with oauth._lock:
                oauth.access = f"access_{exchange_calls}"
                oauth.expiry = time.time() + 3600
            return oauth.access

        oauth._exchange = mock_exchange

        # Start multiple threads to call token()
        threads = []
        results = []
        def get_token():
            results.append(oauth.token())

        for _ in range(5):
            t = threading.Thread(target=get_token)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # _exchange should only be called once because of double-checked locking
        self.assertEqual(exchange_calls, 1)
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertEqual(r, "access_1")

if __name__ == "__main__":
    unittest.main()
