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
        def mock_on_refresh(s): pass

        oauth = GoogleOAuth(settings, mock_on_refresh)

        mock_load_secret.return_value = "fake_refresh_token"

        call_count = 0
        def fake_exchange(data):
            nonlocal call_count
            import time
            time.sleep(0.1)  # Artificially widen the race window
            call_count += 1
            oauth.access = f"token_{call_count}"
            oauth.expiry = time.time() + 3600
            return oauth.access

        with patch.object(oauth, "_exchange", side_effect=fake_exchange):
            import threading

            results = []
            def worker():
                try:
                    results.append(oauth.token())
                except Exception as e:
                    results.append(e)

            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Expect _exchange to be called only once
            self.assertEqual(call_count, 1)
            # All threads should get the same token
            self.assertEqual(len(results), 5)
            for r in results:
                self.assertEqual(r, "token_1")

if __name__ == "__main__":
    unittest.main()
