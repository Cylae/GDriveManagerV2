import unittest
from gdsm.domain.models import Settings

class TestSettingsValidation(unittest.TestCase):
    def test_invalid_concurrency(self):
        with self.assertRaises(ValueError):
            Settings(concurrency=0).validate()
        with self.assertRaises(ValueError):
            Settings(concurrency=9).validate()

    def test_invalid_retries(self):
        with self.assertRaises(ValueError):
            Settings(retries=-1).validate()
        with self.assertRaises(ValueError):
            Settings(retries=11).validate()

    def test_invalid_reserve_bytes(self):
        with self.assertRaises(ValueError):
            Settings(reserve_bytes=-1).validate()

    def test_invalid_language(self):
        with self.assertRaises(ValueError):
            Settings(language='es').validate()

    def test_valid_settings(self):
        # Happy path test
        s = Settings(concurrency=2, retries=5, reserve_bytes=100, language='en')
        try:
            s.validate()
        except ValueError:
            self.fail("validate() raised ValueError unexpectedly!")

if __name__ == '__main__':
    unittest.main()
