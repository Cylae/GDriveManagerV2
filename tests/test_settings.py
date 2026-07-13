import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from gdsm.storage.settings import JsonStore
from gdsm.domain.models import Settings


class TestJsonStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "settings.json"
        self.store = JsonStore(self.store_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_missing_file(self):
        """Test loading settings when the file does not exist."""
        settings = self.store.load()
        self.assertIsInstance(settings, Settings)
        self.assertEqual(settings.language, "fr") # Default

    def test_load_corrupt_file(self):
        """Test loading settings when the file is corrupt."""
        self.store_path.write_text("invalid json")
        settings = self.store.load()
        self.assertIsInstance(settings, Settings)
        self.assertEqual(settings.language, "fr")
        self.assertTrue(self.store_path.with_suffix(".json.corrupt").exists())

    def test_save_happy_path(self):
        """Test saving settings normally."""
        settings = Settings(language="en", concurrency=4)
        self.store.save(settings)

        self.assertTrue(self.store_path.exists())
        data = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.assertEqual(data["language"], "en")
        self.assertEqual(data["concurrency"], 4)

    @patch("os.replace")
    def test_save_cleans_up_temp_file_on_error(self, mock_replace):
        """Test that temp file is unlinked if os.replace fails."""
        mock_replace.side_effect = OSError("Mocked replace failure")
        settings = Settings()

        with self.assertRaises(OSError):
            self.store.save(settings)

        # The temp file should have been unlinked in the finally block.
        # We can verify this by checking that no file matching .config-* exists in the directory.
        temp_files = list(Path(self.temp_dir.name).glob(".config-*"))
        self.assertEqual(len(temp_files), 0, "Temporary file was not cleaned up!")

if __name__ == "__main__":
    unittest.main()
