import unittest
import threading
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
    def test_thread_safe_token_fetch(self, mock_load_secret):
        mock_load_secret.return_value = "dummy_refresh_token"
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        call_count = [0]

        def dummy_exchange(data):
            # simulate network delay
            import time
            time.sleep(0.1)
            call_count[0] += 1
            # modify state explicitly
            with oauth._lock:
                oauth.access = "fresh_token"
                oauth.expiry = time.time() + 3600
            return "fresh_token"

        oauth._exchange = dummy_exchange

        results = []
        def fetch_token():
            results.append(oauth.token())

        threads = [threading.Thread(target=fetch_token) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(call_count[0], 1)
        self.assertEqual(results, ["fresh_token"] * 5)

    def test_exchange_race_condition(self):
        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)

        # We'll patch urlopen and json.load inside _exchange
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_res = MagicMock()
            mock_urlopen.return_value.__enter__.return_value = mock_res
            with patch('json.load') as mock_json_load:
                mock_json_load.return_value = {
                    "access_token": "fresh_token",
                    "expires_in": 3600,
                    "refresh_token": "new_refresh_token"
                }

                # Mock save_secret to simulate logout happening concurrently
                with patch('gdsm.services.oauth.save_secret') as mock_save_secret:
                    def simulate_concurrent_logout(*args):
                        oauth.logout()
                    mock_save_secret.side_effect = simulate_concurrent_logout

                    with patch('gdsm.services.oauth.delete_secret'):
                        # Call _exchange directly
                        returned_token = oauth._exchange({"dummy": "data"})

                        # Verify the token is returned even if logout cleared the class state
                        self.assertEqual(returned_token, "fresh_token")
                        # State should be cleared due to concurrent logout
                        self.assertEqual(oauth.access, "")
                        self.assertEqual(oauth.expiry, 0)


if __name__ == "__main__":
    unittest.main()
