import json
import os
import tempfile
import time
from pathlib import Path
from ..domain.models import DriveItem

CACHE_VERSION = 1


class InventoryCache:
    def __init__(self, cache_file: Path, ttl: int = 3600):
        self.cache_file = cache_file
        self.ttl = ttl

    def load(self) -> list[DriveItem] | None:
        if not self.cache_file.exists():
            return None

        try:
            mtime = self.cache_file.stat().st_mtime
            if time.time() - mtime > self.ttl:
                return None

            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("version") != CACHE_VERSION:
                return None

            items = []
            for d in data.get("items", []):
                d["parents"] = tuple(d.get("parents", []))
                items.append(DriveItem(**d))
            return items
        except Exception:
            return None

    def save(self, items: list[DriveItem]):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=".cache-", dir=self.cache_file.parent, text=False
        )
        try:
            data = {"version": CACHE_VERSION, "items": [i.__dict__ for i in items]}
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.cache_file)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
