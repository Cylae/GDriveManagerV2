import unittest
from unittest.mock import MagicMock

from gdsm.domain.models import DriveItem
from gdsm.services.drive_api import DriveApi


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
        self.assertEqual(self.api.resolve_path("3"), "/folder1/file")


if __name__ == "__main__":
    unittest.main()


class DriveSafetyTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        import tempfile
        from pathlib import Path

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "file"
        self.path.write_bytes(b"hello")
        self.item = DriveItem(
            "1",
            "file",
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
        self.api = DriveApi(MagicMock())
        self.metadata = {
            "size": "5",
            "md5Checksum": self.item.md5,
            "trashed": False,
            "capabilities": {"canTrash": True},
        }

    def response(self, data):
        import io
        import json

        return io.BytesIO(json.dumps(data).encode())

    def test_inventory_uses_file_size_instead_of_quota_bytes(self):
        from unittest.mock import patch

        data = {
            "files": [
                {
                    "id": "1",
                    "name": "file",
                    "mimeType": "text/plain",
                    "size": "5",
                    "quotaBytesUsed": "5000",
                }
            ]
        }
        with patch.object(self.api, "_request", return_value=self.response(data)):
            self.assertEqual(self.api._fetch_all_items()[0].size, 5)

    def test_trash_requires_current_metadata_and_local_verification(self):
        from unittest.mock import patch

        with (
            patch.object(
                self.api, "_request", return_value=self.response(self.metadata)
            ),
            patch.object(self.api, "trash") as trash,
        ):
            self.api.trash_verified(self.item, self.path)
        trash.assert_called_once_with(self.item, cancel=None)

    def test_remote_change_blocks_trash(self):
        from unittest.mock import patch

        self.metadata["md5Checksum"] = "changed"
        with (
            patch.object(
                self.api, "_request", return_value=self.response(self.metadata)
            ),
            patch.object(self.api, "trash") as trash,
            self.assertRaisesRegex(ValueError, "changed"),
        ):
            self.api.trash_verified(self.item, self.path)
        trash.assert_not_called()

    def test_local_change_after_confirmation_blocks_trash(self):
        from unittest.mock import patch

        self.path.write_bytes(b"wrong")
        with (
            patch.object(
                self.api, "_request", return_value=self.response(self.metadata)
            ),
            patch.object(self.api, "trash") as trash,
            self.assertRaisesRegex(ValueError, "MD5"),
        ):
            self.api.trash_verified(self.item, self.path)
        trash.assert_not_called()

    def test_cancellation_after_metadata_blocks_trash(self):
        import threading
        from unittest.mock import patch

        cancel = threading.Event()

        def metadata(*args, **kwargs):
            cancel.set()
            return self.response(self.metadata)

        with (
            patch.object(self.api, "_request", side_effect=metadata),
            patch.object(self.api, "trash") as trash,
            self.assertRaises(InterruptedError),
        ):
            self.api.trash_verified(self.item, self.path, cancel=cancel)
        trash.assert_not_called()

    def test_native_file_cannot_be_trashed_by_verified_path(self):
        from unittest.mock import patch

        self.item.is_native = True
        with (
            patch.object(self.api, "_request") as network,
            self.assertRaises(ValueError),
        ):
            self.api.trash_verified(self.item, self.path)
        network.assert_not_called()
