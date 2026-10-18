import unittest

from gdsm.ui.app import App


class AppTests(unittest.TestCase):
    def test_sanitize_csv_value(self):
        self.assertEqual(App._sanitize_csv_value(None, "normal"), "normal")
        self.assertEqual(
            App._sanitize_csv_value(None, "=cmd|' /C calc'!A0"), "'=cmd|' /C calc'!A0"
        )
        self.assertEqual(App._sanitize_csv_value(None, "+1+2"), "'+1+2")
        self.assertEqual(App._sanitize_csv_value(None, "-1-2"), "'-1-2")
        self.assertEqual(App._sanitize_csv_value(None, "@SUM(A1:A2)"), "'@SUM(A1:A2)")
        self.assertEqual(App._sanitize_csv_value(None, None), "")
        self.assertEqual(App._sanitize_csv_value(None, 123), "123")


class WorkerSafetyTests(unittest.TestCase):
    def setUp(self):
        import queue
        import threading
        from unittest.mock import Mock

        from gdsm.domain.models import Settings

        self.app = object.__new__(App)
        self.app.events = queue.Queue()
        self.app.cancel = threading.Event()
        self.app.closing = False
        self.app.settings = Settings(reserve_bytes=0)
        self.app._api = Mock()
        self.app.log = Mock()
        self.app.root = Mock()

    def item(self, native=False):
        from gdsm.domain.models import DriveItem

        return DriveItem(
            "1", "doc", "text/plain", 5, "abc", "", "", (), True, True, False, native
        )

    def test_api_and_oauth_are_reused(self):
        self.assertIs(self.app.api(), self.app.api())

    def test_workspace_is_never_offered_for_trash(self):
        from unittest.mock import patch

        with (
            patch("gdsm.ui.app.TransferEngine") as engine,
            patch.object(self.app, "_ask_user") as ask,
        ):
            engine.return_value.download_many.return_value = []
            self.app._trash_worker([self.item(native=True)], ".")
        ask.assert_not_called()
        self.app._api.trash_verified.assert_not_called()

    def test_cancel_while_waiting_for_confirmation_blocks_trash(self):
        from unittest.mock import patch

        item = self.item()

        def answer(*args):
            self.app.cancel.set()
            return "Yes"

        with (
            patch("gdsm.ui.app.TransferEngine") as engine,
            patch.object(self.app, "_ask_user", side_effect=answer),
        ):
            engine.return_value.download_many.return_value = [
                (item, ("verified", "file", "ok"))
            ]
            self.app._trash_worker([item], ".")
        self.app._api.trash_verified.assert_not_called()

    def test_background_prompt_uses_only_event_queue(self):
        import threading

        results = []
        worker = threading.Thread(
            target=lambda: results.append(
                self.app._ask_user("title", "question", ["Yes", "No"])
            ),
            daemon=True,
        )
        worker.start()
        kind, payload = self.app.events.get(timeout=2)
        self.assertEqual(kind, "ask")
        payload[3].put("Yes")
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, ["Yes"])
        self.assertEqual(self.app.root.mock_calls, [])

    def test_busy_operation_cannot_reset_cancellation(self):
        from unittest.mock import Mock

        self.app.busy = True
        self.app.status = Mock()
        self.app.cancel.set()
        self.assertFalse(self.app._start_worker(Mock()))
        self.assertTrue(self.app.cancel.is_set())

    def test_progress_sums_concurrent_transfers(self):
        from dataclasses import replace

        first, second = self.item(), replace(self.item(), id="2")
        progress, _ = self.app._make_progress_callback([(first, None), (second, None)])
        progress(first, 3, 5, 1)
        progress(second, 4, 5, 1)
        self.app.events.get_nowait()
        _, payload = self.app.events.get_nowait()
        self.assertEqual(payload[1:3], (7, 10))
