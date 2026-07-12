import tempfile
import unittest
from pathlib import Path
from gdsm.domain.models import DriveItem, Settings
from unittest.mock import patch, MagicMock
from gdsm.utils.paths import safe_name, safe_target, unique_target, ensure_space
from gdsm.services.verification import verify_binary


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = Path(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def test_reserved(self):
        self.assertEqual(safe_name("CON.txt"), "_CON.txt")

    def test_invalid(self):
        self.assertEqual(safe_name("a<b>c"), "a_b_c")

    def test_traversal(self):
        with self.assertRaises(ValueError):
            safe_target(str(self.root), "..\\secret")

    def test_collision(self):
        p = self.root / "x.txt"
        p.write_text("x")
        self.assertTrue(str(unique_target(p)).endswith("x (1).txt"))

    def test_verification(self):
        p = self.root / "x.bin"
        p.write_bytes(b"hello")
        import hashlib

        item = DriveItem(
            "1",
            "x.bin",
            "application/octet-stream",
            5,
            hashlib.md5(b"hello").hexdigest(),
            "",
            "",
            (),
            True,
            True,
            False,
            False,
        )
        self.assertEqual(verify_binary(item, p)[1], "verified")

    def test_settings(self):
        with self.assertRaises(ValueError):
            Settings(concurrency=9).validate()

    @patch("gdsm.utils.paths.shutil.disk_usage")
    def test_ensure_space_success(self, mock_disk_usage):
        mock_usage = MagicMock()
        mock_usage.free = 1000
        mock_disk_usage.return_value = mock_usage
        # Should not raise any exception
        ensure_space(Path("."), 500, 100)

    @patch("gdsm.utils.paths.shutil.disk_usage")
    def test_ensure_space_insufficient(self, mock_disk_usage):
        mock_usage = MagicMock()
        mock_usage.free = 500
        mock_disk_usage.return_value = mock_usage
        with self.assertRaises(OSError) as cm:
            ensure_space(Path("."), 500, 100)
        self.assertIn("insufficient disk space: 500 available, 600 required", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
