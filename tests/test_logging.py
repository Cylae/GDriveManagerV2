import unittest
import tempfile
import json
from pathlib import Path
from gdsm.services.logging import Logger


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = Path(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def test_dual_logging_and_rotation(self):
        jsonl = self.root / "app.jsonl"
        log = self.root / "app.log"
        logger = Logger(jsonl, max_size=50)  # Very small to test rotation

        logger.write("INFO", "first message", foo="bar")
        self.assertTrue(jsonl.exists())
        self.assertTrue(log.exists())

        # Write more to force rotation
        for i in range(10):
            logger.write("INFO", f"spam {i}")

        self.assertTrue(
            (self.root / "app.old").exists()
            or (self.root / "app.jsonl.old").exists()
            or (self.root / "app.log.old").exists()
        )

        # verify content structure
        with open(
            jsonl.with_suffix(".jsonl.old")
            if (self.root / "app.jsonl.old").exists()
            else jsonl,
            "r",
        ) as f:
            line = f.readline()
            data = json.loads(line)
            self.assertEqual(data["level"], "INFO")
            self.assertIn("session_id", data)


if __name__ == "__main__":
    unittest.main()
