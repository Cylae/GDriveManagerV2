import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
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



    @patch("os.open")
    def test_save_keyring_uses_o_excl(self, mock_os_open):
        mock_os_open.return_value = 999
        with patch("builtins.open"), patch("os.fsync"), patch("os.replace"), patch.dict("sys.modules", {"keyring": None}):
            from gdsm.storage.secrets import _save_keyring
            import os

            _save_keyring("test_key", "test_value")

            mock_os_open.assert_called_once()
            args = mock_os_open.call_args.args
            flags = args[1]

            self.assertTrue(bool(flags & os.O_CREAT))
            self.assertTrue(bool(flags & os.O_EXCL))
            self.assertTrue(bool(flags & os.O_WRONLY))

    @patch("os.open")
    def test_save_win32_uses_o_excl(self, mock_os_open):
        mock_os_open.return_value = 999
        with patch("builtins.open"), patch("os.fsync"), patch("os.replace"):
            def mock_crypt(*args):
                return True

            with patch("gdsm.storage.secrets.sys.platform", "win32"):
                from gdsm.storage.secrets import _save_win32
                import os
                import ctypes

                with patch("ctypes.windll", create=True) as mock_windll, patch("ctypes.string_at") as mock_string_at:
                    mock_windll.crypt32.CryptProtectData.side_effect = mock_crypt
                    mock_string_at.return_value = b"encrypted"

                    _save_win32("test_key", "test_value")

                    mock_os_open.assert_called_once()
                    args = mock_os_open.call_args.args
                    flags = args[1]

                    self.assertTrue(bool(flags & os.O_CREAT))
                    self.assertTrue(bool(flags & os.O_EXCL))
                    self.assertTrue(bool(flags & os.O_WRONLY))

if __name__ == "__main__":
    unittest.main()
