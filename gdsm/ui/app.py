import csv
import heapq
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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
        self.events = queue.Queue()
        self.stats = SessionStats()
        self.cancel = threading.Event()
        self.root = tk.Tk()
        self.root.title("GDrive Space Manager — project_v0.3")
        self.root.geometry("1250x760")
        if self.settings.theme == "dark":
            self.root.tk_setPalette(background='#333', foreground='white')
        else:
            self.root.tk_setPalette(background='white', foreground='black')
        self._widgets()
        self.root.after(100, self._drain)
        self.status.set("Checking cache...")
        threading.Thread(target=self._startup_worker, daemon=True).start()

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
        for c, w in zip(cols, (250, 300, 230, 100, 160, 150)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, stretch=c in ("name", "path", "type"))
        main_paned.add(self.tree, weight=3)

        top_items_frame = ttk.LabelFrame(main_paned, text="Top largest items")
        self.top_items_tree = ttk.Treeview(
            top_items_frame, columns=("name", "size"), show="headings", selectmode="none", height=5
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
            except Exception:
                lst.sort(reverse=reverse)
            for index, (val, k) in enumerate(lst):
                self.tree.move(k, "", index)
            self.tree.heading(col, command=lambda: sort_column(col, not reverse))

        for c in cols:
            self.tree.heading(
                c, text=c.title(), command=lambda _c=c: sort_column(_c, False)
            )

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
        import platform
        import subprocess

        path = str(self.home.absolute())
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def api(self):
        oauth = GoogleOAuth(self.settings, lambda s: self.store.save(s))
        return DriveApi(oauth)

    def choose(self):
        x = filedialog.askdirectory(initialdir=self.dest.get() or str(Path.home()))
        if x:
            self.dest.set(x)
            self.settings.destination = x
            self.store.save(self.settings)

    def settings_dialog(self):
        from .settings_dialog import SettingsDialog

        d = SettingsDialog(self.root, self.settings, self.store)
        self.root.wait_window(d.top)

    def refresh(self):
        self.cancel.clear()
        self.status.set("Loading Drive inventory...")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _startup_worker(self):
        try:
            res = self.api().inventory(cancel=self.cancel, force_refresh=False)
            if res:
                items, source = res
                self.events.put(("items", (items, source)))
            else:
                self.events.put(("status", "Ready. Click Refresh to load from Drive."))
        except Exception as e:
            self.events.put(("error", str(e)))

    def _refresh_worker(self):
        try:
            res = self.api().inventory(cancel=self.cancel, force_refresh=True)
            if res:
                items, source = res
                self.events.put(("items", (items, source)))
        except Exception as e:
            self.events.put(("error", str(e)))

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
            self.top_items_tree.insert("", "end", iid=str(idx), values=(it.name, it.size))

    def selected(self):
        return [self.items[int(x)] for x in self.tree.selection()]

    def download(self):
        chosen = [x for x in self.selected() if not x.is_folder]
        if not chosen:
            return messagebox.showinfo("GDrive", "Select one or more files.")
        if not self.dest.get() or not Path(self.dest.get()).is_dir():
            return messagebox.showerror("GDrive", "Choose an existing destination.")
        self.cancel.clear()
        self.status.set("Downloading...")
        threading.Thread(
            target=self._download_worker, args=(chosen,), daemon=True
        ).start()

    def _make_progress_callback(self, jobs):
        total = sum(i.size for i, _ in jobs)
        state = [0]

        def progress(item, current, size, speed, chunk=0):
            self.events.put(
                ("progress", (item.name, state[0] + current, total, speed, chunk))
            )

        def add_done(amount):
            state[0] += amount

        return progress, add_done

    def _download_worker(self, chosen):
        try:
            api = self.api()
            engine = TransferEngine(api, self.settings, self.log)
            jobs = []
            exports = []
            for i in chosen:
                if i.is_native:
                    exports.append((i, safe_target(self.dest.get(), i.name)))
                    continue
                jobs.append((i, safe_target(self.dest.get(), i.name)))

            for item, target in exports:
                status, path, detail = export_workspace_file(api, item, target)
                self.events.put(("queue", (item.name, status, detail)))

            progress, add_done = self._make_progress_callback(jobs)

            for item, result in engine.download_many(jobs, self.cancel, progress):
                add_done(
                    item.size if result[0] in ("verified", "already_verified") else 0
                )
                self.events.put(("queue", (item.name, result[0], result[2])))
            self.events.put(("status", "Queue complete"))
        except Exception as e:
            self.events.put(("error", str(e)))

    def trash(self):
        chosen = [x for x in self.selected() if x.can_trash]
        if not chosen:
            return
        if not self.dest.get() or not Path(self.dest.get()).is_dir():
            return messagebox.showerror(
                "GDrive", "Choose an existing destination for download before trashing."
            )
        threading.Thread(target=self._trash_worker, args=(chosen,), daemon=True).start()

    def _trash_worker(self, chosen):
        try:
            api = self.api()
            engine = TransferEngine(api, self.settings, self.log)
            jobs = []
            for i in chosen:
                if i.is_native:
                    target = safe_target(self.dest.get(), i.name)
                    status, path, detail = export_workspace_file(api, i, target)
                    if status == "exported_unverifiable":
                        resp_queue = queue.Queue()
                        def ask_export():
                            class CustomDialog:
                                def __init__(self, parent):
                                    self.top = tk.Toplevel(parent)
                                    self.top.title("Confirm Trash Workspace Export")
                                    ttk.Label(
                                        self.top,
                                        text=f"Exported Workspace file {i.name}.\nMD5 cannot be verified. Are you sure you want to trash it?",
                                    ).pack(padx=20, pady=10)
                                    self.result = "No"
                                    btn_frame = ttk.Frame(self.top)
                                    btn_frame.pack(pady=10)

                                    def set_res(val):
                                        self.result = val
                                        self.top.destroy()

                                    ttk.Button(
                                        btn_frame, text="Yes", command=lambda: set_res("Yes")
                                    ).pack(side="left", padx=5)
                                    ttk.Button(
                                        btn_frame, text="No", command=lambda: set_res("No")
                                    ).pack(side="left", padx=5)
                                    self.top.wait_window()

                            d = CustomDialog(self.root)
                            resp_queue.put(d.result)

                        self.root.after_idle(ask_export)
                        if resp_queue.get() == "Yes":
                            api.trash(i)
                            self.events.put(("queue", (i.name, "trashed", "Moved to Drive Trash")))
                        else:
                            self.events.put(("queue", (i.name, "skipped", "User cancelled trash of export")))
                    else:
                        self.events.put(("queue", (i.name, "skipped", f"Export failed: {detail}")))
                    continue
                jobs.append((i, safe_target(self.dest.get(), i.name)))

            progress, add_done = self._make_progress_callback(jobs)

            yes_to_all = False
            for item, result in engine.download_many(jobs, self.cancel, progress):
                status, path, detail = result
                add_done(item.size if status in ("verified", "already_verified") else 0)

                if status in ("verified", "already_verified"):
                    if not yes_to_all:
                        resp_queue = queue.Queue()

                        def ask():
                            class CustomDialog:
                                def __init__(self, parent):
                                    self.top = tk.Toplevel(parent)
                                    self.top.title("Confirm Trash")
                                    ttk.Label(
                                        self.top,
                                        text=f"Trash verified file {item.name}?",
                                    ).pack(padx=20, pady=10)
                                    self.result = "No"
                                    btn_frame = ttk.Frame(self.top)
                                    btn_frame.pack(pady=10)

                                    def set_res(val):
                                        self.result = val
                                        self.top.destroy()

                                    ttk.Button(
                                        btn_frame,
                                        text="Yes",
                                        command=lambda: set_res("Yes"),
                                    ).pack(side="left", padx=5)
                                    ttk.Button(
                                        btn_frame,
                                        text="Yes to all",
                                        command=lambda: set_res("Yes to all"),
                                    ).pack(side="left", padx=5)
                                    ttk.Button(
                                        btn_frame,
                                        text="No",
                                        command=lambda: set_res("No"),
                                    ).pack(side="left", padx=5)
                                    ttk.Button(
                                        btn_frame,
                                        text="No to all",
                                        command=lambda: set_res("No to all"),
                                    ).pack(side="left", padx=5)
                                    self.top.wait_window()

                            d = CustomDialog(self.root)
                            resp_queue.put(d.result)

                        self.root.after_idle(ask)
                        ans = resp_queue.get()

                        if ans == "No to all":
                            break
                        elif ans == "Yes to all":
                            yes_to_all = True
                            ans = "Yes"
                    else:
                        ans = "Yes"

                    if ans == "Yes":
                        api.trash(item)
                        self.events.put(
                            ("queue", (item.name, "trashed", "Moved to Drive Trash"))
                        )
                    else:
                        self.events.put(
                            ("queue", (item.name, "skipped", "User cancelled trash"))
                        )
                else:
                    self.events.put(
                        (
                            "queue",
                            (item.name, "skipped", f"Verification failed: {detail}"),
                        )
                    )

            self.events.put(("status", "Trash operation complete"))
        except Exception as e:
            self.events.put(("error", str(e)))

    def _sanitize_csv_value(self, value):
        if value is None:
            return ""
        s = str(value)
        if s.startswith(("=", "+", "-", "@")):
            return "'" + s
        return s

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
                w.writerow([sanitize_csv_field(v) for v in self.queue.item(child)["values"]])
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
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "items":
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
                    elif state == "error":
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

        self.stats_label.set(
            f"Stats: {self.stats.items_count} items | {self.stats.bytes_transferred / 1024 / 1024:.2f} MB transferred | {self.stats.avg_throughput / 1024 / 1024:.2f} MB/s"
        )
        self.root.after(100, self._drain)

    def run(self):
        self.root.mainloop()
