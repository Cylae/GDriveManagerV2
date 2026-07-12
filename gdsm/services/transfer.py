from __future__ import annotations
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..domain.models import DriveItem, Settings
from ..utils.paths import ensure_space, unique_target
from ..services.verification import verify_binary


class TransferEngine:
    def __init__(self, api, settings: Settings, log):
        self.api = api
        self.s = settings
        self.log = log

    def download(
        self, item: DriveItem, target: Path, cancel, progress=lambda *x, **kw: None
    ):
        if item.is_native:
            return (
                "exported_unverifiable",
                str(target),
                "Workspace export is not implemented in this binary path",
            )
        if not item.can_download or item.size <= 0:
            return "skipped", str(target), "item cannot be downloaded"
        target.parent.mkdir(parents=True, exist_ok=True)
        ensure_space(target.parent, item.size, self.s.reserve_bytes)
        if target.exists():
            ok, state, _, detail = verify_binary(item, target)
            if ok:
                return "already_verified", str(target), detail
            target = unique_target(target, self.s.auto_rename)
        partial = Path(str(target) + ".gdsm.partial")
        try:
            for attempt in range(self.s.retries + 1):
                try:
                    self._copy(item, partial, cancel, progress)
                    break
                except (urllib.error.URLError, TimeoutError, OSError):
                    if attempt == self.s.retries:
                        raise
                    time.sleep(min(60, 2**attempt) + 0.2)
            ok, state, sha, detail = verify_binary(item, partial)
            if not ok:
                raise OSError(detail)
            os.replace(partial, target)
            self.log.write(
                "INFO",
                "download validated",
                name=item.name,
                target=str(target),
                sha256=sha,
            )
            return "verified", str(target), detail
        except Exception:
            if not self.s.keep_partial:
                partial.unlink(missing_ok=True)
            raise

    def _copy(self, item, partial, cancel, progress):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > item.size:
            partial.unlink()
            offset = 0
        req = self.api.download_request(item, offset)
        with urllib.request.urlopen(req, timeout=60) as response:
            if offset and response.status == 200:
                partial.unlink(missing_ok=True)
                offset = 0
            if offset and response.status != 206:
                raise OSError("server rejected HTTP Range resume")
            with partial.open("ab" if offset else "wb") as out:
                done = offset
                start = time.monotonic()
                while True:
                    if cancel.is_set():
                        raise InterruptedError("cancelled")
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
                    done += len(block)
                    seconds = max(0.001, time.monotonic() - start)
                    speed = (done - offset) / seconds
                    progress(item, done, item.size, speed, len(block))
        if partial.stat().st_size != item.size:
            raise OSError("incomplete download")

    def download_many(self, jobs, cancel, progress):
        with ThreadPoolExecutor(max_workers=self.s.concurrency) as pool:
            futures = {
                pool.submit(self.download, item, target, cancel, progress): item
                for item, target in jobs
            }
            for future in as_completed(futures):
                item = futures[future]
                try:
                    yield item, future.result()
                except InterruptedError:
                    yield item, ("cancelled", "", "cancelled")
                except Exception as e:
                    yield item, ("failed", "", str(e))
