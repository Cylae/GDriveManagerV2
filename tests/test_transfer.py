import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from gdsm.domain.models import DriveItem, Settings
from gdsm.services.transfer import TransferEngine


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = Path(self.d.name)
        self.api = MagicMock()
        self.settings = Settings(reserve_bytes=0)
        self.log = MagicMock()
        self.cancel = MagicMock()
        self.cancel.is_set.return_value = False
        self.engine = TransferEngine(self.api, self.settings, self.log)

    def tearDown(self):
        self.d.cleanup()

    def test_never_trash_if_workspace_export(self):
        item = DriveItem(
            "1",
            "doc",
            "application/vnd.google-apps.document",
            0,
            None,
            "",
            "",
            (),
            False,
            True,
            False,
            True,
        )
        status, target, detail = self.engine.download(
            item, self.root / "doc", self.cancel
        )
        self.assertEqual(status, "exported_unverifiable")
        self.assertEqual(self.api.trash.call_count, 0)

    def test_never_trash_if_no_md5(self):
        item = DriveItem(
            "2",
            "file.bin",
            "application/octet-stream",
            5,
            None,
            "",
            "",
            (),
            True,
            True,
            False,
            False,
        )

        # We need a dummy download that succeeds but verification fails due to no MD5
        def mock_download(req, timeout):
            class R:
                status = 200

                def read(self, *a):
                    self.read = lambda *a: b""
                    return b"hello"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return R()

        self.api.download_request.return_value = MagicMock()
        import urllib.request

        orig_urlopen = urllib.request.urlopen
        urllib.request.urlopen = mock_download

        try:
            status, target, detail = self.engine.download(
                item, self.root / "file.bin", self.cancel
            )
            self.assertEqual(status, "verified")
        except OSError as e:
            self.assertIn("Drive MD5 is absent", str(e))
        finally:
            urllib.request.urlopen = orig_urlopen
        self.assertEqual(self.api.trash.call_count, 0)

    def test_cancellation_mid_download(self):
        item = DriveItem(
            "3",
            "large.bin",
            "application/octet-stream",
            100,
            "abc",
            "",
            "",
            (),
            True,
            True,
            False,
            False,
        )

        def mock_download(req, timeout):
            class R:
                status = 200

                def read(self_, *a):
                    self.cancel.is_set.return_value = True
                    return b"A" * 10

                def __enter__(self_):
                    return self_

                def __exit__(self_, *a):
                    pass

            return R()

        self.api.download_request.return_value = MagicMock()
        import urllib.request

        orig_urlopen = urllib.request.urlopen
        urllib.request.urlopen = mock_download

        try:
            with self.assertRaises(InterruptedError):
                self.engine.download(item, self.root / "large.bin", self.cancel)
        finally:
            urllib.request.urlopen = orig_urlopen


if __name__ == "__main__":
    unittest.main()
