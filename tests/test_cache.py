import unittest
import tempfile
import time
import os
from pathlib import Path
from gdsm.domain.models import DriveItem
from gdsm.services.cache import InventoryCache, CACHE_VERSION


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.cache_file = Path(self.d.name) / "cache.json"
        self.cache = InventoryCache(self.cache_file, ttl=2)

    def tearDown(self):
        self.d.cleanup()

    def test_save_load_hit(self):
        item = DriveItem(
            "1", "f", "text", 0, None, "", "", ("2",), False, False, False, False
        )
        self.cache.save([item])
        loaded = self.cache.load()
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, "1")
        self.assertEqual(loaded[0].parents, ("2",))

    def test_load_expiry(self):
        item = DriveItem(
            "1", "f", "text", 0, None, "", "", (), False, False, False, False
        )
        self.cache.save([item])
        # Force old mtime
        os.utime(self.cache_file, (time.time() - 5, time.time() - 5))
        self.assertIsNone(self.cache.load())

    def test_version_mismatch(self):
        import json

        with open(self.cache_file, "w") as f:
            json.dump({"version": CACHE_VERSION - 1, "items": []}, f)
        self.assertIsNone(self.cache.load())

    def test_corruption(self):
        self.cache_file.write_text("{bad json")
        self.assertIsNone(self.cache.load())


if __name__ == "__main__":
    unittest.main()
