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
    @patch("gdsm.services.oauth.urllib.request.urlopen")
    def test_concurrent_refresh(self, mock_urlopen, mock_load_secret, mock_delete_secret):
        import io
        import json
        import threading

        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)
        mock_load_secret.return_value = "fake_refresh_token"

        call_count = 0
        started = threading.Event()
        proceed = threading.Event()

        class MockResponse:
            def __init__(self, data):
                self.data = data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return self.data

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            started.set()
            proceed.wait()
            return io.BytesIO(json.dumps({"access_token": "new_token", "expires_in": 3600}).encode())

        mock_urlopen.side_effect = side_effect

        def worker(results, index):
            results[index] = oauth.token()

        results = [None, None]
        t1 = threading.Thread(target=worker, args=(results, 0))
        t2 = threading.Thread(target=worker, args=(results, 1))

        t1.start()
        started.wait()
        t2.start()

        # t2 should be blocked on the refresh_lock
        import time
        time.sleep(0.1)
        proceed.set()

        t1.join()
        t2.join()

        self.assertEqual(results[0], "new_token")
        self.assertEqual(results[1], "new_token")
        self.assertEqual(call_count, 1)

    @patch("gdsm.services.oauth.delete_secret")
    @patch("gdsm.services.oauth.load_secret")
    @patch("gdsm.services.oauth.urllib.request.urlopen")
    def test_logout_concurrent_with_refresh(self, mock_urlopen, mock_load_secret, mock_delete_secret):
        import io
        import json
        import threading

        settings = Settings(client_id="test_client_id")
        oauth = GoogleOAuth(settings, lambda s: None)
        mock_load_secret.return_value = "fake_refresh_token"

        started = threading.Event()
        proceed = threading.Event()

        def side_effect(*args, **kwargs):
            started.set()
            proceed.wait()
            return io.BytesIO(json.dumps({"access_token": "new_token", "expires_in": 3600}).encode())

        mock_urlopen.side_effect = side_effect

        results = [None]
        def worker(results):
            results[0] = oauth.token()

        t1 = threading.Thread(target=worker, args=(results,))
        t1.start()
        started.wait()

        # While refresh is blocked, call logout in another thread
        def logout_worker():
            oauth.logout()

        t2 = threading.Thread(target=logout_worker)
        t2.start()

        # ensure t2 started and is waiting on lock
        import time
        time.sleep(0.1)
        proceed.set()

        t1.join()
        t2.join()

        # token() should return the valid token it just fetched
        self.assertEqual(results[0], "new_token")
        # but oauth instance should have access token cleared by logout
        self.assertEqual(oauth.access, "")
        mock_delete_secret.assert_called_once_with("refresh_token")

if __name__ == "__main__":
    unittest.main()
