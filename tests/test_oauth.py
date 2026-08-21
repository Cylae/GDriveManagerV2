import threading
import time
import unittest
from unittest.mock import MagicMock, patch
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

    @patch("gdsm.services.oauth.load_secret", return_value="test_refresh_token")
    def test_concurrent_refresh_only_calls_exchange_once(self, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        mock_on_refresh = MagicMock()
        oauth = GoogleOAuth(settings, mock_on_refresh)

        # We will mock _exchange to sleep slightly to simulate I/O,
        # then set the tokens so subsequent checks see them as valid.
        def mock_exchange(data):
            time.sleep(0.1)
            with oauth._lock:
                oauth.access = "new_test_access_token"
                oauth.expiry = time.time() + 3600
            return oauth.access

        results = []
        def worker():
            try:
                token = oauth.token()
                results.append(token)
            except Exception as e:
                results.append(str(e))

        with patch.object(oauth, "_exchange", side_effect=mock_exchange) as mock_exchange_method:
            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Verify that all threads got the correct token
            self.assertEqual(len(results), 5)
            self.assertTrue(all(r == "new_test_access_token" for r in results))

            # Verify that _exchange was only called once despite 5 threads requesting a token
            # simultaneously when it was expired/empty.
            mock_exchange_method.assert_called_once()

if __name__ == "__main__":
    unittest.main()
