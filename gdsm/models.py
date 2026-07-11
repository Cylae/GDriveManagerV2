from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass(frozen=True)
class DriveItem:
    id: str; name: str; mime_type: str; size: int; md5: Optional[str]
    modified: str; owner: str; parents: tuple[str,...]; can_download: bool; can_trash: bool
    is_folder: bool; is_native: bool; drive_path: str = ''

@dataclass
class Settings:
    client_id: str = ''; refresh_token: str = ''; destination: str = ''
    concurrency: int = 2; retries: int = 5; reserve_bytes: int = 2 * 1024**3
    auto_rename: bool = True; keep_partial: bool = True; language: str = 'fr'
    def validate(self):
        if not 1 <= self.concurrency <= 8: raise ValueError('concurrency must be between 1 and 8')
        if not 0 <= self.retries <= 10: raise ValueError('retries must be between 0 and 10')
        if self.reserve_bytes < 0: raise ValueError('reserve_bytes must be non-negative')
        if self.language not in ('fr','en'): raise ValueError('language must be fr or en')
    def to_json(self): return asdict(self)
    @classmethod
    def from_json(cls, raw):
        allowed={k:v for k,v in raw.items() if k in cls.__dataclass_fields__}
        obj=cls(**allowed); obj.validate(); return obj
