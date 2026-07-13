import unittest
from gdsm.ui.app import App

class AppTests(unittest.TestCase):
    def test_sanitize_csv_value(self):
        # Test function without instantiating App
        self.assertEqual(App._sanitize_csv_value(None, "normal"), "normal")
        self.assertEqual(App._sanitize_csv_value(None, "=cmd|' /C calc'!A0"), "'=cmd|' /C calc'!A0")
        self.assertEqual(App._sanitize_csv_value(None, "+1+2"), "'+1+2")
        self.assertEqual(App._sanitize_csv_value(None, "-1-2"), "'-1-2")
        self.assertEqual(App._sanitize_csv_value(None, "@SUM(A1:A2)"), "'@SUM(A1:A2)")
        self.assertEqual(App._sanitize_csv_value(None, None), "")
        self.assertEqual(App._sanitize_csv_value(None, 123), "123")
