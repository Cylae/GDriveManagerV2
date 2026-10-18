import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gdsm.utils.files import atomic_write, publish_new_file


class FileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_failed_atomic_replace_preserves_previous_file(self):
        target = self.root / "settings.json"
        target.write_bytes(b"old")
        with (
            patch("gdsm.utils.files.os.replace", side_effect=OSError("failure")),
            self.assertRaises(OSError),
        ):
            atomic_write(target, b"new")
        self.assertEqual(target.read_bytes(), b"old")
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_temporary_descriptor_is_closed_before_replace(self):
        real_fdopen, real_replace = (os.fdopen, os.replace)
        streams = []

        def fdopen(*args, **kwargs):
            stream = real_fdopen(*args, **kwargs)
            streams.append(stream)
            return stream

        def replace(source, target):
            self.assertTrue(all(stream.closed for stream in streams))
            return real_replace(source, target)

        with (
            patch("gdsm.utils.files.os.fdopen", side_effect=fdopen),
            patch("gdsm.utils.files.os.replace", side_effect=replace),
        ):
            atomic_write(self.root / "data", b"new")
        self.assertEqual((self.root / "data").read_bytes(), b"new")

    @unittest.skipIf(os.name == "nt", "POSIX mode bits")
    def test_atomic_file_has_private_permissions(self):
        target = self.root / "secret"
        atomic_write(target, b"secret")
        self.assertEqual(target.stat().st_mode & 511, 384)

    def test_exclusive_publication_handles_late_collision(self):
        source, target = (self.root / "partial", self.root / "file")
        source.write_bytes(b"new")
        target.write_bytes(b"old")
        result = publish_new_file(source, target)
        self.assertEqual(target.read_bytes(), b"old")
        self.assertEqual(result.read_bytes(), b"new")
        self.assertNotEqual(target, result)
        self.assertFalse(source.exists())

    def test_no_rename_preserves_source_and_existing_target(self):
        source, target = (self.root / "partial", self.root / "file")
        source.write_bytes(b"new")
        target.write_bytes(b"old")
        with self.assertRaises(FileExistsError):
            publish_new_file(source, target, auto_rename=False)
        self.assertEqual(source.read_bytes(), b"new")
        self.assertEqual(target.read_bytes(), b"old")

    def test_filesystem_without_hard_links_uses_exclusive_copy(self):
        source, target = (self.root / "partial", self.root / "file")
        source.write_bytes(b"new")
        with patch(
            "gdsm.utils.files.os.link",
            side_effect=OSError(errno.ENOTSUP, "unsupported"),
        ):
            result = publish_new_file(source, target)
        self.assertEqual(result.read_bytes(), b"new")
        self.assertFalse(source.exists())

    def test_failed_fallback_copy_removes_incomplete_destination(self):
        source, target = (self.root / "partial", self.root / "file")
        source.write_bytes(b"new")
        with (
            patch(
                "gdsm.utils.files.os.link",
                side_effect=OSError(errno.ENOTSUP, "unsupported"),
            ),
            patch(
                "gdsm.utils.files.shutil.copyfileobj", side_effect=OSError("disk full")
            ),
            self.assertRaises(OSError),
        ):
            publish_new_file(source, target)
        self.assertFalse(target.exists())
        self.assertEqual(source.read_bytes(), b"new")
