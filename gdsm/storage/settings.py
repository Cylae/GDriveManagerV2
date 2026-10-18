from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import Settings
from ..utils.files import atomic_write
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
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
            self.path.replace(self.path.with_suffix(self.path.suffix + ".corrupt"))
            return Settings()

    def save(self, settings: Settings) -> None:
        settings.validate()
        atomic_write(
            self.path,
            json.dumps(settings.to_json(), indent=2).encode("utf-8"),
            ".config-",
        )
