import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from gdsm.domain.models import DriveItem
from gdsm.services.export import export_workspace_file


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = Path(self.d.name)
        self.api = MagicMock()

    def tearDown(self):
        self.d.cleanup()

    def _mock_response(self, content=b"data", status=200, headers=None):

        class R:
            def __init__(self):
                self.status = status
                self.headers = headers or {}

            def read(self, *a):
                return content

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        return R()

    def test_export_document_docx(self):
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
            False,
            False,
            True,
        )
        self.api._request.return_value = self._mock_response(b"docx_data")
        status, path, _detail = export_workspace_file(self.api, item, self.root / "doc")
        self.assertEqual(status, "exported_unverifiable")
        self.assertTrue(path.endswith(".docx"))
        self.assertEqual((self.root / "doc.docx").read_bytes(), b"docx_data")

    def test_export_unknown_fallback_pdf(self):
        item = DriveItem(
            "1",
            "form",
            "application/vnd.google-apps.form",
            0,
            None,
            "",
            "",
            (),
            False,
            False,
            False,
            True,
        )
        self.api._request.return_value = self._mock_response(b"pdf_data")
        status, path, _detail = export_workspace_file(
            self.api, item, self.root / "form"
        )
        self.assertEqual(status, "exported_unverifiable")
        self.assertTrue(path.endswith(".pdf"))

    def test_export_size_limit(self):
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
            False,
            False,
            True,
        )
        self.api._request.return_value = self._mock_response(b"x" * 11)
        status, _path, detail = export_workspace_file(
            self.api, item, self.root / "doc", max_bytes=10
        )
        self.assertEqual(status, "error")
        self.assertIn("exceeds size limit", detail)

    def test_export_size_limit_header(self):
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
            False,
            False,
            True,
        )
        self.api._request.return_value = self._mock_response(
            b"x", headers={"Content-Length": "11"}
        )
        status, _path, detail = export_workspace_file(
            self.api, item, self.root / "doc", max_bytes=10
        )
        self.assertEqual(status, "error")
        self.assertIn("exceeds size limit", detail)


if __name__ == "__main__":
    unittest.main()


class ExportSafetyTests(unittest.TestCase):
    setUp = ExportTests.setUp
    tearDown = ExportTests.tearDown
    _mock_response = ExportTests._mock_response

    def workspace(self):
        return DriveItem(
            "1",
            "report.v2",
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

    def test_existing_export_survives(self):
        target = self.root / "report.v2.docx"
        target.write_bytes(b"original")
        self.api._request.return_value = self._mock_response(b"new")
        status, path, _ = export_workspace_file(
            self.api, self.workspace(), self.root / "report.v2"
        )
        self.assertEqual(status, "exported_unverifiable")
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(Path(path).read_bytes(), b"new")
        self.assertEqual(Path(path).name, "report.v2 (1).docx")

    def test_cancel_after_response_never_creates_export(self):
        import threading
        from unittest.mock import patch

        cancel = threading.Event()
        response = self._mock_response(b"new")

        def read(*args):
            cancel.set()
            return b"new"

        with patch.object(response, "read", side_effect=read):
            self.api._request.return_value = response
            with self.assertRaises(InterruptedError):
                export_workspace_file(
                    self.api, self.workspace(), self.root / "report", cancel=cancel
                )
        self.assertEqual(list(self.root.iterdir()), [])

    def test_collision_with_rename_disabled_preserves_original(self):
        target = self.root / "report.v2.docx"
        target.write_bytes(b"original")
        self.api._request.return_value = self._mock_response(b"new")
        status, _, _ = export_workspace_file(
            self.api, self.workspace(), self.root / "report.v2", auto_rename=False
        )
        self.assertEqual(status, "error")
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual(list(self.root.iterdir()), [target])
