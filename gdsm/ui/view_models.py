import time
from dataclasses import dataclass


@dataclass
class SessionStats:
    start_time: float = 0.0
    items_count: int = 0
    total_size: int = 0
    downloaded_count: int = 0
    verified_count: int = 0
    ignored_count: int = 0
    error_count: int = 0
    bytes_transferred: int = 0

    def reset(self):
        self.start_time = time.monotonic()
        self.items_count = 0
        self.total_size = 0
        self.downloaded_count = 0
        self.verified_count = 0
        self.ignored_count = 0
        self.error_count = 0
        self.bytes_transferred = 0

    @property
    def avg_throughput(self) -> float:
        duration = time.monotonic() - self.start_time
        if duration <= 0:
            return 0.0
        return self.bytes_transferred / duration

    @property
    def session_duration(self) -> float:
        return time.monotonic() - self.start_time
