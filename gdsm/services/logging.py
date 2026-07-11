from __future__ import annotations
import json
from pathlib import Path


class Logger:
    def __init__(self, path: Path, max_size: int = 5 * 1024 * 1024):
        self.path = path
        self.max_size = max_size
        self.session_id = __import__("uuid").uuid4().hex

    def _rotate(self, target: Path):
        if target.exists() and target.stat().st_size >= self.max_size:
            import os

            try:
                os.replace(target, target.with_suffix(target.suffix + ".old"))
            except OSError:
                pass

    def write(self, level: str, message: str, **data):
        import datetime

        self.path.parent.mkdir(parents=True, exist_ok=True)

        jsonl_path = self.path
        log_path = self.path.with_suffix(".log")

        self._rotate(jsonl_path)
        self._rotate(log_path)

        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        row = {
            "timestamp_utc": ts,
            "session_id": self.session_id,
            "level": level,
            "message": message,
            "data": data,
        }

        # Write JSONL
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        # Write human-readable text
        text_line = f"[{ts}] [{level}] {message}"
        if data:
            text_line += f" | {json.dumps(data, ensure_ascii=False)}"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(text_line + "\n")
