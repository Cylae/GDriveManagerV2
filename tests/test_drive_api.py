import unittest
from gdsm.domain.models import DriveItem
from gdsm.services.drive_api import DriveApi
from unittest.mock import MagicMock


class DriveApiTests(unittest.TestCase):
    def setUp(self):
        self.api = DriveApi(MagicMock())
        self.api.items_by_id = {}

    def test_resolve_root_item(self):
        item = DriveItem(
            "1",
            "root_file",
            "text/plain",
            0,
            None,
            "",
            "",
            (),
            False,
            False,
            False,
            False,
        )
        self.api.items_by_id["1"] = item
        self.assertEqual(self.api.resolve_path("1"), "/root_file")

    def test_resolve_nested(self):
        root = DriveItem(
            "1",
            "folder",
            "application/vnd.google-apps.folder",
            0,
            None,
            "",
            "",
            (),
            False,
            False,
            True,
            False,
        )
        child = DriveItem(
            "2",
            "file",
            "text/plain",
            0,
            None,
            "",
            "",
            ("1",),
            False,
            False,
            False,
            False,
        )
        self.api.items_by_id = {"1": root, "2": child}
        self.assertEqual(self.api.resolve_path("2"), "/folder/file")

    def test_resolve_orphaned(self):
        child = DriveItem(
            "2",
            "file",
            "text/plain",
            0,
            None,
            "",
            "",
            ("999",),
            False,
            False,
            False,
            False,
        )
        self.api.items_by_id = {"2": child}
        self.assertEqual(self.api.resolve_path("2"), "<orphaned>/file")

    def test_resolve_cycle(self):
        a = DriveItem(
            "1",
            "a",
            "application/vnd.google-apps.folder",
            0,
            None,
            "",
            "",
            ("2",),
            False,
            False,
            True,
            False,
        )
        b = DriveItem(
            "2",
            "b",
            "application/vnd.google-apps.folder",
            0,
            None,
            "",
            "",
            ("1",),
            False,
            False,
            True,
            False,
        )
        self.api.items_by_id = {"1": a, "2": b}
        path = self.api.resolve_path("1")
        self.assertTrue(path.startswith("<cycle-detected>"))

    def test_resolve_shortcut(self):
        target = DriveItem(
            "1", "target", "text/plain", 0, None, "", "", (), False, False, False, False
        )
        shortcut = DriveItem(
            "2",
            "shortcut",
            "application/vnd.google-apps.shortcut",
            0,
            None,
            "",
            "",
            (),
            False,
            False,
            False,
            False,
        )
        shortcut.__dict__["shortcut_target"] = "1"
        self.api.items_by_id = {"1": target, "2": shortcut}
        self.assertEqual(self.api.resolve_path("2"), "/target (shortcut)")



    def test_resolve_multi_parent(self):
        root1 = DriveItem(
            "1",
            "folder1",
            "application/vnd.google-apps.folder",
            0,
            None,
            "",
            "",
            (),
            False,
            False,
            True,
            False,
        )
        root2 = DriveItem(
            "2",
            "folder2",
            "application/vnd.google-apps.folder",
            0,
            None,
            "",
            "",
            (),
            False,
            False,
            True,
            False,
        )
        child = DriveItem(
            "3",
            "file",
            "text/plain",
            0,
            None,
            "",
            "",
            ("1", "2"),
            False,
            False,
            False,
            False,
        )
        self.api.items_by_id = {"1": root1, "2": root2, "3": child}
        # Assuming it resolves the first parent as primary, per naive implementation
        self.assertEqual(self.api.resolve_path("3"), "/folder1/file")

if __name__ == "__main__":
    unittest.main()
