import hashlib
import io
import tempfile
import threading
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from gdsm.domain.models import DriveItem, Settings
from gdsm.services.transfer import TransferEngine


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


def binary(identity="1", data=b"hello", name="file.bin"):
    return DriveItem(
        identity,
        name,
        "application/octet-stream",
        len(data),
        hashlib.md5(data, usedforsecurity=False).hexdigest(),
        "",
        "",
        (),
        True,
        True,
        False,
        False,
    )


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.api, self.log = (Mock(), Mock())
        self.settings = Settings(reserve_bytes=0, retries=1)
        self.engine = TransferEngine(self.api, self.settings, self.log)
        self.cancel = threading.Event()

    def test_never_trash_if_workspace_export(self):
        item = binary()
        item.is_native = True
        status, _, _ = self.engine.download(item, self.root / "doc", self.cancel)
        self.assertEqual(status, "exported_unverifiable")
        self.api.trash.assert_not_called()

    def test_missing_md5_never_downloads_or_authorizes_trash(self):
        item = binary()
        item.md5 = None
        with patch("gdsm.services.transfer.urllib.request.urlopen") as network:
            status, _, _ = self.engine.download(item, self.root / "file", self.cancel)
        self.assertEqual(status, "skipped")
        network.assert_not_called()
        self.api.trash.assert_not_called()

    def test_cancellation_mid_download_is_not_retried(self):
        self.api.download_request.return_value = "request"
        with (
            patch(
                "gdsm.services.transfer.urllib.request.urlopen",
                return_value=Response(b"hello"),
            ) as network,
            patch("gdsm.utils.retry._safe_sleep") as sleep,
            self.assertRaises(InterruptedError),
        ):
            self.engine.download(
                binary(),
                self.root / "file",
                self.cancel,
                lambda *args: self.cancel.set(),
            )
        network.assert_called_once()
        sleep.assert_not_called()
        self.assertFalse((self.root / "file").exists())
        self.api.trash.assert_not_called()

    def test_pre_cancelled_download_has_no_side_effects(self):
        self.cancel.set()
        with self.assertRaises(InterruptedError):
            self.engine.download(binary(), self.root / "file", self.cancel)
        self.assertEqual(list(self.root.iterdir()), [])
        self.api.download_request.assert_not_called()

    def test_existing_file_is_not_overwritten(self):
        target = self.root / "file.bin"
        target.write_bytes(b"original")
        with patch(
            "gdsm.services.transfer.urllib.request.urlopen",
            return_value=Response(b"hello"),
        ):
            status, path, _ = self.engine.download(binary(), target, self.cancel)
        self.assertEqual(status, "verified")
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(Path(path).read_bytes(), b"hello")
        self.assertNotEqual(Path(path), target)

    def test_same_name_concurrent_downloads_both_survive(self):
        items = [binary("a", b"first"), binary("b", b"second")]
        self.api.download_request.side_effect = lambda item, offset: item.id
        payloads = {"a": b"first", "b": b"second"}
        with (
            patch(
                "gdsm.services.transfer.urllib.request.urlopen",
                side_effect=lambda request, **kw: Response(payloads[request]),
            ),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            futures = [
                pool.submit(
                    self.engine.download, item, self.root / "same.bin", self.cancel
                )
                for item in items
            ]
            results = [future.result(timeout=3) for future in futures]
        paths = [Path(result[1]) for result in results]
        self.assertEqual(len(set(paths)), 2)
        self.assertEqual({path.read_bytes() for path in paths}, {b"first", b"second"})
        self.assertEqual(list(self.root.glob("*.partial")), [])

    def test_complete_partial_is_verified_without_network(self):
        item, target = (binary(), self.root / "file.bin")
        identity = hashlib.sha256((item.id + "\x00" + target.name).encode()).hexdigest()
        (self.root / f".gdsm-{identity}.partial").write_bytes(b"hello")
        with patch("gdsm.services.transfer.urllib.request.urlopen") as network:
            self.assertEqual(
                self.engine.download(item, target, self.cancel)[0], "verified"
            )
        network.assert_not_called()
        self.assertEqual(target.read_bytes(), b"hello")

    def test_resume_checks_content_range(self):
        partial = self.root / "partial"
        partial.write_bytes(b"he")
        with patch(
            "gdsm.services.transfer.urllib.request.urlopen",
            return_value=Response(b"llo", 206, {"Content-Range": "bytes 2-4/5"}),
        ):
            self.engine._copy(binary(), partial, Mock(), cancel=self.cancel)
        self.assertEqual(partial.read_bytes(), b"hello")
        self.api.download_request.assert_called_once_with(binary(), 2)

    def test_bad_content_range_retains_partial(self):
        partial = self.root / "partial"
        partial.write_bytes(b"he")
        with (
            patch(
                "gdsm.services.transfer.urllib.request.urlopen",
                return_value=Response(b"llo", 206, {"Content-Range": "bytes 1-3/5"}),
            ),
            self.assertRaisesRegex(OSError, "Content-Range"),
        ):
            self.engine._copy(binary(), partial, Mock(), cancel=self.cancel)
        self.assertEqual(partial.read_bytes(), b"he")

    def test_404_is_not_retried(self):
        error = urllib.error.HTTPError("", 404, "Not Found", {}, io.BytesIO())
        with (
            patch(
                "gdsm.services.transfer.urllib.request.urlopen", side_effect=error
            ) as network,
            self.assertRaises(urllib.error.HTTPError),
        ):
            self.engine.download(binary(), self.root / "file", self.cancel)
        network.assert_called_once()

    @patch("gdsm.utils.retry._safe_sleep")
    def test_503_retries_once(self, sleep):
        error = urllib.error.HTTPError(
            "", 503, "Unavailable", {"Retry-After": "0"}, io.BytesIO()
        )
        with patch(
            "gdsm.services.transfer.urllib.request.urlopen",
            side_effect=[error, Response(b"hello")],
        ) as network:
            status, _, _ = self.engine.download(
                binary(), self.root / "file", self.cancel
            )
        self.assertEqual(status, "verified")
        self.assertEqual(network.call_count, 2)
        sleep.assert_called_once_with(0.0, self.cancel)

    def test_md5_mismatch_never_publishes_corrupt_file(self):
        with (
            patch(
                "gdsm.services.transfer.urllib.request.urlopen",
                return_value=Response(b"wrong"),
            ),
            self.assertRaisesRegex(OSError, "MD5"),
        ):
            self.engine.download(binary(), self.root / "file", self.cancel)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_empty_binary_can_be_verified(self):
        with patch(
            "gdsm.services.transfer.urllib.request.urlopen", return_value=Response(b"")
        ):
            status, path, _ = self.engine.download(
                binary(data=b""), self.root / "empty", self.cancel
            )
        self.assertEqual(status, "verified")
        self.assertEqual(Path(path).read_bytes(), b"")
