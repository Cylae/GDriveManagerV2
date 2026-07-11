import tkinter as tk
from tkinter import ttk
from ..domain.models import Settings
from ..storage.settings import JsonStore


class SettingsDialog:
    def __init__(self, parent: tk.Tk, settings: Settings, store: JsonStore):
        self.settings = settings
        self.store = store
        self.top = tk.Toplevel(parent)
        self.top.title("Settings")

        self.client_id = tk.StringVar(value=self.settings.client_id)
        self.lang = tk.StringVar(value=self.settings.language)
        self.concurrency = tk.IntVar(value=self.settings.concurrency)
        self.retries = tk.IntVar(value=self.settings.retries)
        self.auto_rename = tk.BooleanVar(value=self.settings.auto_rename)
        self.keep_partial = tk.BooleanVar(value=self.settings.keep_partial)

        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self.top, padding=20)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Google OAuth Client ID:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        ttk.Entry(f, textvariable=self.client_id, width=50).grid(
            row=0, column=1, pady=5
        )

        ttk.Label(f, text="Language (en/fr):").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            f, textvariable=self.lang, values=["en", "fr"], state="readonly"
        ).grid(row=1, column=1, sticky="w", pady=5)

        ttk.Label(f, text="Concurrency (1-8):").grid(
            row=2, column=0, sticky="w", pady=5
        )
        ttk.Spinbox(f, from_=1, to=8, textvariable=self.concurrency, width=5).grid(
            row=2, column=1, sticky="w", pady=5
        )

        ttk.Label(f, text="Retries (0-10):").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Spinbox(f, from_=0, to=10, textvariable=self.retries, width=5).grid(
            row=3, column=1, sticky="w", pady=5
        )

        ttk.Checkbutton(
            f, text="Auto-rename to avoid collisions", variable=self.auto_rename
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Checkbutton(
            f, text="Keep partial downloads on error", variable=self.keep_partial
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Button(f, text="Save", command=self.save).grid(
            row=6, column=0, columnspan=2, pady=15
        )

    def save(self):
        try:
            self.settings.client_id = self.client_id.get().strip()
            self.settings.language = self.lang.get()
            self.settings.concurrency = self.concurrency.get()
            self.settings.retries = self.retries.get()
            self.settings.auto_rename = self.auto_rename.get()
            self.settings.keep_partial = self.keep_partial.get()
            self.store.save(self.settings)
            self.top.destroy()
        except ValueError as e:
            from tkinter import messagebox

            messagebox.showerror("Settings Error", str(e), parent=self.top)
