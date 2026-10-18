from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class DriveItem:
    id: str
    name: str
    mime_type: str
    size: int
    md5: str | None
    modified: str
    owner: str
    parents: tuple[str, ...]
    can_download: bool
    can_trash: bool
    is_folder: bool
    is_native: bool
    drive_path: str = ""
    shortcut_target: str = ""


@dataclass
class Settings:
    client_id: str = ""
    destination: str = ""
    concurrency: int = 2
    retries: int = 5
    reserve_bytes: int = 2 * 1024**3
    auto_rename: bool = True
    keep_partial: bool = True
    language: str = "fr"
    theme: str = "light"

    def validate(self):
        for name in ("client_id", "destination", "language", "theme"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a string")
        for name in ("concurrency", "retries", "reserve_bytes"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        for name in ("auto_rename", "keep_partial"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if not 1 <= self.concurrency <= 8:
            raise ValueError("concurrency must be between 1 and 8")
        if not 0 <= self.retries <= 10:
            raise ValueError("retries must be between 0 and 10")
        if self.reserve_bytes < 0:
            raise ValueError("reserve_bytes must be non-negative")
        if self.language not in ("fr", "en"):
            raise ValueError("language must be fr or en")
        if self.theme not in ("light", "dark"):
            raise ValueError("theme must be light or dark")

    def to_json(self):
        return asdict(self)

    @classmethod
    def from_json(cls, raw):
        if not isinstance(raw, dict):
            raise TypeError("settings must be a JSON object")
        allowed = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        obj = cls(**allowed)
        obj.validate()
        return obj
