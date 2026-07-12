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
