import tempfile
import unittest
from pathlib import Path

from gdsm.domain.models import DriveItem
from gdsm.services.cache import InventoryCache


class WindowsCacheTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.cache_file = Path(self.d.name) / "cache.json"
        self.cache = InventoryCache(self.cache_file, ttl=2)

    def tearDown(self):
        self.d.cleanup()

    def test_no_double_carriage_return(self):
        item = DriveItem(
            "1", "f", "text", 0, None, "", "", ("2",), False, False, False, False
        )
        self.cache.save([item])
        with open(self.cache_file, "rb") as f:
            content = f.read()
        self.assertNotIn(b"\r\r\n", content)


if __name__ == "__main__":
    unittest.main()
