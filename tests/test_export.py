import unittest
import tempfile
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

        status, path, detail = export_workspace_file(self.api, item, self.root / "doc")
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

        status, path, detail = export_workspace_file(self.api, item, self.root / "form")
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
        # return more than 10 bytes
        self.api._request.return_value = self._mock_response(b"x" * 11)

        status, path, detail = export_workspace_file(
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

        status, path, detail = export_workspace_file(
            self.api, item, self.root / "doc", max_bytes=10
        )
        self.assertEqual(status, "error")
        self.assertIn("exceeds size limit", detail)


if __name__ == "__main__":
    unittest.main()
