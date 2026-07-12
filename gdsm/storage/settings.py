from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from ..domain.models import Settings
from .secrets import save_secret


class JsonStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if "refresh_token" in data:
                token = data.pop("refresh_token")
                if token:
                    save_secret("refresh_token", token)
                self.save(Settings.from_json(data))
            return Settings.from_json(data)
        except (json.JSONDecodeError, ValueError, TypeError):
            self.path.replace(self.path.with_suffix(self.path.suffix + ".corrupt"))
            return Settings()

    def save(self, settings: Settings) -> None:
        settings.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".config-{uuid.uuid4().hex}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(settings.to_json(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()
