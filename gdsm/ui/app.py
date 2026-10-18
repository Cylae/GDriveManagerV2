import csv
import heapq
import queue
import sys
import threading
import tkinter as tk
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from ..services.cache import InventoryCache
from ..services.drive_api import DriveApi
from ..services.export import export_workspace_file
from ..services.logging import Logger
from ..services.oauth import GoogleOAuth
from ..services.transfer import TransferEngine
from ..storage.settings import JsonStore
from ..utils.paths import safe_target
from ..utils.security import sanitize_csv_field
from .view_models import SessionStats


class App:
    def __init__(self):
        self.home = Path.home() / ".gdrive-space-manager"
        self.store = JsonStore(self.home / "config.json")
        self.settings = self.store.load()
        self.log = Logger(self.home / "operations.jsonl")
        self.items = []
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.stats = SessionStats()
        self.stats.reset()
        self.cancel = threading.Event()
        self._api = DriveApi(GoogleOAuth(self.settings, self.store.save))
        self.busy = True
        self.closing = False
        self.root = tk.Tk()
        self.root.title("GDrive Space Manager")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.geometry("1250x760")
        if self.settings.theme == "dark":
            self.root.tk_setPalette(background="#333", foreground="white")
        else:
            self.root.tk_setPalette(background="white", foreground="black")
        self._widgets()
        self.root.after(100, self._drain)
        self.status.set("Checking cache...")
        threading.Thread(
            target=self._run_worker, args=(self._startup_worker, ()), daemon=True
        ).start()

    def _widgets(self):
        self._setup_toolbar()
        self._setup_controls()
        self._setup_treeviews()
        self._setup_status_bar()

    def _setup_toolbar(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        for text, cmd in [
            ("Refresh", self.refresh),
            ("Settings", self.settings_dialog),
            ("Download selected", self.download),
            ("Trash selected", self.trash),
            ("Cancel", self.cancel.set),
            ("Export CSV", self.export_csv),
            ("Export Queue", self.export_queue_csv),
            ("Export Report", self.export_session_report),
            ("Logs", self.open_logs),
        ]:
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=3)

    def _setup_controls(self):
        row = ttk.Frame(self.root, padding=(8, 0))
        row.pack(fill="x")
        ttk.Label(row, text="Destination").pack(side="left")
        self.dest = tk.StringVar(value=self.settings.destination)
        ttk.Entry(row, textvariable=self.dest).pack(
            side="left", fill="x", expand=True, padx=5
        )
        ttk.Button(row, text="Choose", command=self.choose).pack(side="left")
        self.search = tk.StringVar()

        self._search_timer = None

        def on_search_change(*args):
            if self._search_timer:
                self.root.after_cancel(self._search_timer)
            self._search_timer = self.root.after(300, self.render)

        self.search.trace_add("write", on_search_change)

        ttk.Entry(row, textvariable=self.search, width=30).pack(side="left", padx=5)

    def _setup_treeviews(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_paned.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("name", "path", "type", "size", "modified", "owner")
        self.tree = ttk.Treeview(
            main_paned, columns=cols, show="headings", selectmode="extended"
        )
        for c, w in zip(cols, (250, 300, 230, 100, 160, 150), strict=True):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, stretch=c in ("name", "path", "type"))
        main_paned.add(self.tree, weight=3)

        top_items_frame = ttk.LabelFrame(main_paned, text="Top largest items")
        self.top_items_tree = ttk.Treeview(
            top_items_frame,
            columns=("name", "size"),
            show="headings",
            selectmode="none",
            height=5,
        )
        self.top_items_tree.heading("name", text="Name")
        self.top_items_tree.heading("size", text="Size")
        self.top_items_tree.column("name", width=600, stretch=True)
        self.top_items_tree.column("size", width=150, stretch=False)
        self.top_items_tree.pack(fill="both", expand=True, padx=5, pady=5)
        main_paned.add(top_items_frame, weight=1)

        def sort_column(col, reverse):
            lst = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
            try:
                if col == "size":
                    lst.sort(key=lambda t: int(t[0]), reverse=reverse)
                else:
                    lst.sort(reverse=reverse)
            except (ValueError, TypeError):
                lst.sort(reverse=reverse)
            for index, (_, k) in enumerate(lst):
                self.tree.move(k, "", index)
            self.tree.heading(col, command=lambda: sort_column(col, not reverse))

        for c in cols:
            self.tree.heading(c, text=c.title(), command=partial(sort_column, c, False))

    def _setup_status_bar(self):
        self.progress = ttk.Progressbar(self.root, maximum=100)
        self.progress.pack(fill="x", padx=8)
        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status, padding=8).pack(anchor="w")
        self.stats_label = tk.StringVar(
            value="Stats: 0 items | 0.0 MB transferred | 0.0 MB/s"
        )
        ttk.Label(self.root, textvariable=self.stats_label, padding=(8, 0, 8, 8)).pack(
            anchor="w"
        )
        self.queue = ttk.Treeview(
            self.root, columns=("name", "state", "detail"), show="headings", height=8
        )
        [self.queue.heading(c, text=c.title()) for c in ("name", "state", "detail")]
        self.queue.pack(fill="x", padx=8, pady=8)

    def open_logs(self):
        import os
        import subprocess

        path = str(self.home.absolute())
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def api(self):
        return self._api

    def _run_worker(self, target, args):
        try:
            target(*args)
        except InterruptedError:
            self.events.put(("status", "Operation cancelled"))
        except Exception as error:  # noqa: BLE001 - report worker failures through the UI queue
            self.events.put(("error", str(error)))
        finally:
            self.events.put(("idle", None))

    def _start_worker(self, target, args=()):
        if self.busy:
            self.status.set(
                "An operation is running. Cancel it or wait for completion."
            )
            return False
        self.busy = True
        self.cancel.clear()
        self.stats.reset()
        threading.Thread(
            target=self._run_worker, args=(target, args), daemon=True
        ).start()
        return True

    def close(self):
        self.closing = True
        self.cancel.set()
        self.root.destroy()

    def choose(self):
        x = filedialog.askdirectory(initialdir=self.dest.get() or str(Path.home()))
        if x:
            self.dest.set(x)
            self.settings.destination = x
            self.store.save(self.settings)

    def settings_dialog(self):
        if self.busy:
            self.status.set("Wait for the current operation before changing settings.")
            return
        from .settings_dialog import SettingsDialog

        previous_client = self.settings.client_id
        dialog = SettingsDialog(self.root, self.settings, self.store, self.logout)
        self.root.wait_window(dialog.top)
        if self.settings.client_id != previous_client and not self.busy:
            self.logout()

    def logout(self):
        self._start_worker(self._logout_worker)

    def _logout_worker(self):
        self._api.oauth.logout()
        (self.home / "inventory_cache.json").unlink(missing_ok=True)
        self._api.items_by_id.clear()
        self._api._path_memo.clear()
        self.events.put(("items", ([], "signed out")))
        self.events.put(("status", "Signed out. Click Refresh to sign in."))

    def refresh(self):
        if self._start_worker(self._refresh_worker):
            self.status.set("Loading Drive inventory...")

    def _startup_worker(self):
        # Startup only reads local cache; sign-in is an explicit Refresh action.
        items = InventoryCache(self.home / "inventory_cache.json").load()
        if items is not None:
            self.events.put(("items", (items, "cached")))
        else:
            self.events.put(("status", "Ready. Click Refresh to load from Drive."))

    def _refresh_worker(self):
        items, source = self.api().inventory(cancel=self.cancel, force_refresh=True)
        self.events.put(("items", (items, source)))

    def render(self):
        q = self.search.get().lower()
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(self.items):
            if q and (
                q not in item.name.lower()
                and q not in item.mime_type.lower()
                and q not in item.drive_path.lower()
            ):
                continue
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    item.name,
                    item.drive_path,
                    item.mime_type,
                    item.size,
                    item.modified,
                    item.owner,
                ),
            )

        self.top_items_tree.delete(*self.top_items_tree.get_children())
        sorted_items = heapq.nlargest(10, self.items, key=lambda x: x.size)
        for idx, it in enumerate(sorted_items):
            self.top_items_tree.insert(
                "", "end", iid=str(idx), values=(it.name, it.size)
            )

    def selected(self):
        return [self.items[int(x)] for x in self.tree.selection()]

    def download(self):
        chosen = [item for item in self.selected() if not item.is_folder]
        if not chosen:
            return messagebox.showinfo("GDrive", "Select one or more files.")
        destination = self.dest.get()
        if not destination or not Path(destination).is_dir():
            return messagebox.showerror("GDrive", "Choose an existing destination.")
        if self._start_worker(self._download_worker, (chosen, destination)):
            self.status.set("Downloading...")

    def _make_progress_callback(self, jobs):
        total = sum(item.size for item, _ in jobs)
        positions = {}
        lock = threading.Lock()

        def progress(item, current, size, speed, chunk=0):
            with lock:
                positions[item.id] = current
                done = sum(positions.values())
            self.events.put(("progress", (item.name, done, total, speed, chunk)))

        def add_done(item, amount):
            with lock:
                positions[item.id] = amount

        return progress, add_done

    def _download_worker(self, chosen, destination):
        api = self.api()
        engine = TransferEngine(api, self.settings, self.log)
        jobs = []
        for item in chosen:
            if self.cancel.is_set():
                raise InterruptedError("cancelled")
            target = safe_target(destination, item.name)
            if item.is_native:
                status, _, detail = export_workspace_file(
                    api,
                    item,
                    target,
                    cancel=self.cancel,
                    auto_rename=self.settings.auto_rename,
                )
                self.events.put(("queue", (item.name, status, detail)))
            else:
                jobs.append((item, target))
        progress, add_done = self._make_progress_callback(jobs)
        for item, result in engine.download_many(jobs, self.cancel, progress):
            add_done(
                item, item.size if result[0] in ("verified", "already_verified") else 0
            )
            self.events.put(("queue", (item.name, result[0], result[2])))
        self.events.put(
            ("status", "Queue cancelled" if self.cancel.is_set() else "Queue complete")
        )

    def _ask_user(self, title, message, buttons):
        responses: queue.Queue[str] = queue.Queue()
        self.events.put(("ask", (title, message, buttons, responses)))
        while not self.cancel.is_set() and not self.closing:
            try:
                return responses.get(timeout=0.1)
            except queue.Empty:
                pass
        return "No to all"

    def _show_prompt(self, title, message, buttons, responses):
        if self.cancel.is_set() or self.closing:
            responses.put("No to all")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text=message, wraplength=600).pack(padx=20, pady=10)
        frame = ttk.Frame(dialog)
        frame.pack(pady=10)
        answer = ["No"]

        def finish(value):
            answer[0] = value
            dialog.destroy()

        for label in buttons:
            ttk.Button(frame, text=label, command=partial(finish, label)).pack(
                side="left", padx=5
            )
        dialog.wait_window()
        responses.put(answer[0])

    def trash(self):
        chosen = [
            item for item in self.selected() if item.can_trash and not item.is_folder
        ]
        if not chosen:
            return
        destination = self.dest.get()
        if not destination or not Path(destination).is_dir():
            return messagebox.showerror(
                "GDrive", "Choose an existing destination for download before trashing."
            )
        if self._start_worker(self._trash_worker, (chosen, destination)):
            self.status.set("Verifying files before Trash...")

    def _trash_worker(self, chosen, destination):
        api = self.api()
        engine = TransferEngine(api, self.settings, self.log)
        jobs = []
        for item in chosen:
            if self.cancel.is_set():
                raise InterruptedError("cancelled")
            if item.is_native or item.is_folder:
                self.events.put(
                    (
                        "queue",
                        (
                            item.name,
                            "skipped",
                            "Workspace files and folders are retained on Drive",
                        ),
                    )
                )
                continue
            jobs.append((item, safe_target(destination, item.name)))
        progress, add_done = self._make_progress_callback(jobs)
        yes_to_all = False
        for item, result in engine.download_many(jobs, self.cancel, progress):
            status, path, detail = result
            add_done(
                item, item.size if status in ("verified", "already_verified") else 0
            )
            if self.cancel.is_set():
                break
            if status not in ("verified", "already_verified"):
                self.events.put(
                    ("queue", (item.name, "skipped", f"Verification failed: {detail}"))
                )
                continue
            answer = (
                "Yes"
                if yes_to_all
                else self._ask_user(
                    "Confirm Trash",
                    f"Trash verified file {item.name}?",
                    ["Yes", "Yes to all", "No", "No to all"],
                )
            )
            if self.cancel.is_set() or answer == "No to all":
                self.cancel.set()
                break
            if answer == "Yes to all":
                yes_to_all = True
                answer = "Yes"
            if answer == "Yes":
                try:
                    api.trash_verified(item, Path(path), cancel=self.cancel)
                except InterruptedError:
                    raise
                except (OSError, ValueError) as error:
                    self.events.put(("queue", (item.name, "failed", str(error))))
                    continue
                self.events.put(
                    ("queue", (item.name, "trashed", "Moved to Drive Trash"))
                )
            else:
                self.events.put(
                    ("queue", (item.name, "skipped", "User declined trash"))
                )
        self.events.put(
            (
                "status",
                "Trash cancelled"
                if self.cancel.is_set()
                else "Trash operation complete",
            )
        )

    def _sanitize_csv_value(self, value):
        return sanitize_csv_field("" if value is None else str(value))

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Name", "Path", "Mime type", "Size", "Modified", "Owner"])
            w.writerows(
                (
                    sanitize_csv_field(x.name),
                    sanitize_csv_field(getattr(x, "drive_path", "")),
                    sanitize_csv_field(x.mime_type),
                    x.size,
                    sanitize_csv_field(x.modified),
                    sanitize_csv_field(x.owner),
                )
                for x in self.items
            )
        self.status.set("CSV exported: " + path)

    def export_queue_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Name", "State", "Detail"])
            for child in self.queue.get_children():
                w.writerow(
                    [sanitize_csv_field(v) for v in self.queue.item(child)["values"]]
                )
        self.status.set("Queue CSV exported: " + path)

    def export_session_report(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text Report", "*.txt")]
        )
        if not path:
            return
        report = f"Session Duration: {self.stats.session_duration:.2f}s\n"
        report += f"Items: {self.stats.items_count}\n"
        report += f"Verified: {self.stats.verified_count}\n"
        report += f"Ignored: {self.stats.ignored_count}\n"
        report += f"Errors: {self.stats.error_count}\n"
        report += f"Bytes Transferred: {self.stats.bytes_transferred}\n"
        report += (
            f"Avg Throughput: {self.stats.avg_throughput / 1024 / 1024:.2f} MB/s\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        self.status.set("Session report exported: " + path)

    def _drain(self):
        if self.closing:
            return
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "idle":
                    self.busy = False
                elif kind == "ask":
                    self._show_prompt(*data)
                elif kind == "items":
                    items, source = data
                    self.items = items
                    self.render()
                    self.status.set(f"{len(items)} items loaded [{source}]")
                    self.stats.items_count = len(items)
                elif kind == "queue":
                    self.queue.insert("", "end", values=data)
                    state = data[1]
                    if state in ("verified", "already_verified"):
                        self.stats.verified_count += 1
                    elif state == "skipped":
                        self.stats.ignored_count += 1
                    elif state in ("error", "failed"):
                        self.stats.error_count += 1
                elif kind == "progress":
                    name, done, total, speed, chunk = data
                    self.stats.bytes_transferred += chunk
                    self.progress["value"] = 0 if not total else done * 100 / total
                    eta_str = ""
                    if speed > 0 and total > done:
                        eta_sec = (total - done) / speed
                        eta_str = f" | ETA: {eta_sec:.0f}s"
                    self.status.set(f"{name} — {speed / 1024 / 1024:.2f} MB/s{eta_str}")
                elif kind == "status":
                    self.status.set(data)
                elif kind == "error":
                    self.status.set(data)
                    messagebox.showerror("GDrive error", data)
        except queue.Empty:
            pass

        if self.closing:
            return
        self.stats_label.set(
            f"Stats: {self.stats.items_count} items | {self.stats.bytes_transferred / 1024 / 1024:.2f} MB transferred | {self.stats.avg_throughput / 1024 / 1024:.2f} MB/s"
        )
        self.root.after(100, self._drain)

    def run(self):
        self.root.mainloop()
