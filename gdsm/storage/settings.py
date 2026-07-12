from __future__ import annotations
import json
import os
import tempfile
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
        fd, tmp = tempfile.mkstemp(prefix=".config-", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(settings.to_json(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
