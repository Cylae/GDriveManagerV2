"""Real Tkinter smoke checks; run with GDSM_GUI_TESTS=1 and a display."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from gdsm.ui.app import App
from gdsm.ui.settings_dialog import SettingsDialog


@unittest.skipUnless(
    os.environ.get("GDSM_GUI_TESTS") == "1", "requires a graphical display"
)
class GuiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        home = patch("pathlib.Path.home", return_value=self.directory)
        home.start()
        self.addCleanup(home.stop)
        self.network = patch(
            "gdsm.services.drive_api.DriveApi._request",
            side_effect=AssertionError("unexpected network access"),
        )
        self.network.start()
        self.addCleanup(self.network.stop)
        self.errors = patch("tkinter.messagebox.showerror")
        self.error = self.errors.start()
        self.addCleanup(self.errors.stop)
        self.app = App()
        self.app.root.withdraw()
        self.addCleanup(self.app.close)
        deadline = time.monotonic() + 5
        while self.app.busy and time.monotonic() < deadline:
            self.app.root.update()
            time.sleep(0.01)
        self.assertFalse(self.app.busy)

    def test_startup_is_local_and_all_widgets_exist(self):
        self.error.assert_not_called()
        self.assertEqual(self.app.tree.get_children(), ())
        self.assertIn("Click Refresh", self.app.status.get())
        self.assertIs(self.app.api(), self.app.api())

    def test_settings_save_is_transactional(self):
        dialog = SettingsDialog(self.app.root, self.app.settings, self.app.store)
        original = self.app.settings.concurrency
        dialog.concurrency.set(9)
        dialog.save()
        self.error.assert_called_once()
        self.assertEqual(self.app.settings.concurrency, original)
        self.assertTrue(dialog.top.winfo_exists())
        dialog.concurrency.set(3)
        dialog.save()
        self.assertEqual(self.app.settings.concurrency, 3)
        self.assertEqual(self.app.store.load().concurrency, 3)
