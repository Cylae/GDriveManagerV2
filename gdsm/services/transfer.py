"""Verified downloads, resumable partials, and collision-safe publication."""

from __future__ import annotations

import hashlib
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..domain.models import DriveItem, Settings
from ..utils.files import publish_new_file
from ..utils.paths import ensure_space
from ..utils.retry import with_retry
from .verification import verify_binary


class TransferEngine:
    def __init__(self, api, settings: Settings, log):
        self.api = api
        self.s = settings
        self.log = log
        self._locks: dict[Path, threading.Lock] = {}
        self._lock = threading.Lock()

    def download(
        self, item: DriveItem, target: Path, cancel, progress=lambda *x, **kw: None
    ):
        if cancel.is_set():
            raise InterruptedError("cancelled")
        if item.is_native:
            return (
                "exported_unverifiable",
                str(target),
                "Workspace export requires the export service",
            )
        if item.is_folder or not item.can_download or item.size < 0:
            return "skipped", str(target), "item cannot be downloaded"
        if not item.md5:
            return "skipped", str(target), "Drive MD5 is absent; retain source"
        target.parent.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256((item.id + "\0" + target.name).encode()).hexdigest()
        partial = target.with_name(f".gdsm-{identity}.partial")
        with self._lock:
            lock = self._locks.setdefault(partial, threading.Lock())
        # Duplicate queue entries cannot append to the same partial concurrently.
        while not lock.acquire(timeout=0.1):
            if cancel.is_set():
                raise InterruptedError("cancelled")
        try:
            if target.is_file() and not target.is_symlink():
                ok, _, _, detail = verify_binary(item, target, cancel=cancel)
                if ok:
                    return "already_verified", str(target), detail
            if os.path.lexists(target) and not self.s.auto_rename:
                raise FileExistsError(str(target))
            if partial.is_symlink():
                raise OSError("refusing a symlink partial file")
            offset = partial.stat().st_size if partial.exists() else 0
            ensure_space(
                target.parent, max(0, item.size - offset), self.s.reserve_bytes
            )
            copy = with_retry(max_retries=self.s.retries)(self._copy)
            copy(item, partial, progress, cancel=cancel)
            ok, _, sha, detail = verify_binary(item, partial, cancel=cancel)
            if not ok:
                # A corrupt partial cannot be repaired by appending to it.
                partial.unlink(missing_ok=True)
                raise OSError(detail)
            if cancel.is_set():
                raise InterruptedError("cancelled")
            final = publish_new_file(partial, target, self.s.auto_rename)
            self.log.write(
                "INFO",
                "download validated",
                name=item.name,
                target=str(final),
                sha256=sha,
            )
            return "verified", str(final), detail
        except Exception:
            if not self.s.keep_partial:
                partial.unlink(missing_ok=True)
            raise
        finally:
            lock.release()

    def _copy(self, item, partial, progress, *, cancel):
        if cancel.is_set():
            raise InterruptedError("cancelled")
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > item.size:
            partial.unlink()
            offset = 0
        # Complete partials are reverified without an invalid bytes=size- request.
        if partial.exists() and offset == item.size:
            return
        request = self.api.download_request(item, offset)
        with urllib.request.urlopen(request, timeout=60) as response:
            if offset and response.status == 200:
                offset = 0
            elif offset:
                if response.status != 206:
                    raise OSError("server rejected HTTP Range resume")
                content_range = response.headers.get("Content-Range", "")
                prefix = f"bytes {offset}-"
                if not content_range.startswith(prefix) or not content_range.endswith(
                    f"/{item.size}"
                ):
                    raise OSError("server returned an inconsistent HTTP Content-Range")
            flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if offset else os.O_TRUNC)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(partial, flags, 0o600)
            with os.fdopen(fd, "ab" if offset else "wb") as output:
                done = offset
                start = time.monotonic()
                while True:
                    if cancel.is_set():
                        raise InterruptedError("cancelled")
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    if done + len(block) > item.size:
                        raise OSError("download exceeds the expected Drive size")
                    output.write(block)
                    done += len(block)
                    speed = (done - offset) / max(0.001, time.monotonic() - start)
                    progress(item, done, item.size, speed, len(block))
                output.flush()
                os.fsync(output.fileno())
        if cancel.is_set():
            raise InterruptedError("cancelled")
        if partial.stat().st_size != item.size:
            raise ConnectionError("incomplete download")

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
                except Exception as error:  # noqa: BLE001 - isolate each worker result
                    yield item, ("failed", "", str(error))
