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
    def test_token_thread_safety(self, mock_load_secret):
        settings = Settings(client_id="test_client_id")
        mock_load_secret.return_value = "dummy_refresh_token"

        def mock_on_refresh(s):
            pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        # We mock _exchange so it doesn't make real network calls
        import threading
        import time

        call_count = 0
        def side_effect(data):
            nonlocal call_count
            call_count += 1
            # Simulate a slow network call
            time.sleep(0.5)
            # Simulate the side effects of _exchange safely updating state
            with oauth._lock:
                oauth.access = "new_access_token"
                oauth.expiry = time.time() + 3600
            return oauth.access

        with patch.object(oauth, "_exchange", side_effect=side_effect):
            threads = []
            results = []

            def thread_target():
                try:
                    res = oauth.token()
                    results.append(res)
                except Exception as e:
                    results.append(e)

            # Start multiple threads simultaneously
            for _ in range(5):
                t = threading.Thread(target=thread_target)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # verify that _exchange was only called once despite 5 threads calling token()
            self.assertEqual(call_count, 1)
            # verify all threads got the correct token
            self.assertEqual(len(results), 5)
            for res in results:
                self.assertEqual(res, "new_access_token")

if __name__ == "__main__":
    unittest.main()
