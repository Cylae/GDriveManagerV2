import unittest
import tempfile
from pathlib import Path
from gdsm.storage.secrets import save_secret, load_secret, delete_secret
from gdsm.storage.settings import JsonStore


class SecretsTests(unittest.TestCase):
    def test_secret_lifecycle(self):
        delete_secret("test_token")
        self.assertIsNone(load_secret("test_token"))
        save_secret("test_token", "my_super_secret")
        self.assertEqual(load_secret("test_token"), "my_super_secret")
        delete_secret("test_token")
        self.assertIsNone(load_secret("test_token"))

    def test_fallback_lifecycle_and_logging(self):
        from unittest.mock import patch

        import sys

        with patch("gdsm.storage.secrets.sys.platform", "linux"):
            # Mock keyring on sys.modules so patch doesn't fail if keyring is absent
            import importlib
            from unittest.mock import MagicMock
            keyring_mock = MagicMock()
            keyring_mock.set_password.side_effect = Exception("mock fail")
            keyring_mock.get_password.side_effect = Exception("mock fail")
            keyring_mock.delete_password.side_effect = Exception("mock fail")

            with patch.dict("sys.modules", {"keyring": keyring_mock}):
                with tempfile.TemporaryDirectory() as d:
                    with patch("os.path.expanduser", return_value=d):
                        with self.assertLogs("gdsm.storage.secrets", level="WARNING") as cm:
                            # 1. Save secret triggers keyring fail + logs warning + writes atomic file
                            save_secret("test_fallback", "fallback_value")
                            self.assertTrue(any("Keyring failed for save" in log for log in cm.output))

                            # 2. Load secret triggers keyring fail + logs warning + reads file
                            val = load_secret("test_fallback")
                            self.assertEqual(val, "fallback_value")
                            self.assertTrue(any("Keyring failed for load" in log for log in cm.output))

                            # 3. Delete secret triggers keyring fail + logs warning + deletes file
                            delete_secret("test_fallback")
                            self.assertTrue(any("Keyring failed for delete" in log for log in cm.output))

                            # 4. Load secret again should return None
                            self.assertIsNone(load_secret("test_fallback"))

    def test_migration(self):
        delete_secret("refresh_token")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            path.write_text('{"client_id": "c1", "refresh_token": "old_token"}')
            store = JsonStore(path)
            s = store.load()
            self.assertEqual(s.client_id, "c1")
            self.assertFalse(hasattr(s, "refresh_token"))
            self.assertEqual(load_secret("refresh_token"), "old_token")
            # verify it was removed from file
            self.assertNotIn("refresh_token", path.read_text())
            delete_secret("refresh_token")


if __name__ == "__main__":
    unittest.main()
