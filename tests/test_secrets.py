import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import keyring

from gdsm.storage import secrets
from gdsm.storage.settings import JsonStore


class SecretsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.home = patch("gdsm.storage.secrets.Path.home", return_value=self.root)
        self.home.start()
        self.addCleanup(self.home.stop)
        self.platform = patch("gdsm.storage.secrets.sys.platform", "linux")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        for name in ("get_password", "set_password"):
            mock = patch(
                f"keyring.{name}",
                side_effect=keyring.errors.NoKeyringError("unavailable"),
            )
            mock.start()
            self.addCleanup(mock.stop)

    def test_secret_lifecycle(self):
        secrets.delete_secret("test_token")
        self.assertIsNone(secrets.load_secret("test_token"))
        with self.assertLogs("gdsm.storage.secrets", level="WARNING") as captured:
            secrets.save_secret("test_token", "private-test-value")
        self.assertNotIn("private-test-value", " ".join(captured.output))
        self.assertEqual(secrets.load_secret("test_token"), "private-test-value")
        secrets.delete_secret("test_token")
        self.assertIsNone(secrets.load_secret("test_token"))

    def test_migration(self):
        path = self.root / "config.json"
        path.write_text('{"client_id":"c1","refresh_token":"old_token"}')
        with self.assertLogs("gdsm.storage.secrets", level="WARNING"):
            settings = JsonStore(path).load()
        self.assertEqual(settings.client_id, "c1")
        self.assertEqual(secrets.load_secret("refresh_token"), "old_token")
        self.assertNotIn("refresh_token", path.read_text())

    def test_fallback_can_be_read_when_keyring_returns_none(self):
        with self.assertLogs("gdsm.storage.secrets", level="WARNING"):
            secrets.save_secret("token", "saved")
        with patch("keyring.get_password", return_value=None):
            self.assertEqual(secrets.load_secret("token"), "saved")

    def test_successful_keyring_save_removes_stale_fallback(self):
        with self.assertLogs("gdsm.storage.secrets", level="WARNING"):
            secrets.save_secret("token", "old")
        path = self.root / ".gdrive-space-manager/.token.secret"
        with patch("keyring.set_password") as save:
            secrets.save_secret("token", "new")
        save.assert_called_once_with("GDriveSpaceManager", "token", "new")
        self.assertFalse(path.exists())

    def test_failed_replace_preserves_previous_secret(self):
        with self.assertLogs("gdsm.storage.secrets", level="WARNING"):
            secrets.save_secret("token", "old")
            with (
                patch("gdsm.utils.files.os.replace", side_effect=OSError("failure")),
                self.assertRaises(OSError),
            ):
                secrets.save_secret("token", "new")
        self.assertEqual(secrets.load_secret("token"), "old")
        self.assertEqual(len(list((self.root / ".gdrive-space-manager").iterdir())), 1)

    def test_delete_failure_is_not_reported_as_success(self):
        with (
            patch("keyring.get_password", return_value="saved"),
            patch(
                "keyring.delete_password",
                side_effect=keyring.errors.KeyringError("locked"),
            ),
            self.assertRaises(keyring.errors.KeyringError),
        ):
            secrets.delete_secret("token")

    def test_credential_path_rejects_traversal(self):
        with self.assertRaises(ValueError):
            secrets.save_secret("../escape", "test")

    @unittest.skipIf(os.name == "nt", "POSIX mode bits")
    def test_fallback_file_permissions_are_private(self):
        with self.assertLogs("gdsm.storage.secrets", level="WARNING"):
            secrets.save_secret("token", "saved")
        path = self.root / ".gdrive-space-manager/.token.secret"
        self.assertEqual(path.stat().st_mode & 511, 384)

    def test_windows_creates_directory_and_persists_only_encrypted_bytes(self):
        with patch("gdsm.storage.secrets._dpapi", return_value=b"encrypted") as dpapi:
            secrets._save_win32("token", "plain")
        dpapi.assert_called_once_with(b"plain", protect=True)
        path = self.root / ".gdrive-space-manager/.token.dpapi"
        self.assertEqual(path.read_bytes(), b"encrypted")
        with patch("gdsm.storage.secrets._dpapi", return_value=b"plain"):
            self.assertEqual(secrets._load_win32("token"), "plain")
        secrets._delete_win32("token")
        self.assertFalse(path.exists())

    @unittest.skipUnless(sys.platform == "win32", "requires Windows DPAPI")
    def test_native_windows_dpapi_roundtrip(self):
        secrets._save_win32("token", "test-roundtrip")
        self.assertEqual(secrets._load_win32("token"), "test-roundtrip")
