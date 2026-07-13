import tempfile
import unittest
from pathlib import Path
from gdsm.storage.settings import JsonStore
from gdsm.domain.models import Settings

class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = Path(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def test_load_corrupt_json(self):
        p = self.root / "settings.json"
        p.write_text("invalid json content", encoding="utf-8")

        store = JsonStore(p)
        settings = store.load()

        self.assertIsInstance(settings, Settings)
        # Original file should be gone
        self.assertFalse(p.exists())
        # Corrupt file should exist
        corrupt_p = p.with_suffix(p.suffix + ".corrupt")
        self.assertTrue(corrupt_p.exists())
        self.assertEqual(corrupt_p.read_text(encoding="utf-8"), "invalid json content")

    def test_load_non_existent(self):
        p = self.root / "does_not_exist.json"
        store = JsonStore(p)
        settings = store.load()

        self.assertIsInstance(settings, Settings)
        self.assertFalse(p.exists())

if __name__ == "__main__":
    unittest.main()
