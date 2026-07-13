import tempfile
import unittest
from pathlib import Path
from gdsm.domain.models import DriveItem, Settings
from gdsm.utils.paths import safe_name, safe_target, unique_target
from gdsm.utils.security import sanitize_csv_field
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
            hashlib.md5(b"hello", usedforsecurity=False).hexdigest(),
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

    def test_sanitize_csv_field(self):
        self.assertEqual(sanitize_csv_field("=1+1"), "'=1+1")
        self.assertEqual(sanitize_csv_field("+1+1"), "'+1+1")
        self.assertEqual(sanitize_csv_field("-1+1"), "'-1+1")
        self.assertEqual(sanitize_csv_field("@SUM(1,1)"), "'@SUM(1,1)")
        self.assertEqual(sanitize_csv_field("\t=1+1"), "'\t=1+1")
        self.assertEqual(sanitize_csv_field("\r=1+1"), "'\r=1+1")
        self.assertEqual(sanitize_csv_field("hello"), "hello")
        self.assertEqual(sanitize_csv_field("1+1"), "1+1")
        self.assertEqual(sanitize_csv_field(""), "")
        self.assertEqual(sanitize_csv_field(123), 123)
        self.assertEqual(sanitize_csv_field(None), None)


if __name__ == "__main__":
    unittest.main()
