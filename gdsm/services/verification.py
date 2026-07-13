from __future__ import annotations
import hashlib
from pathlib import Path
from ..domain.models import DriveItem


def checksums(path: Path, sha256: bool = True, cancel=None) -> tuple[str, str | None]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha = hashlib.sha256() if sha256 else None
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            if cancel and cancel.is_set():
                raise InterruptedError("cancelled")
            md5.update(block)
            if sha:
                sha.update(block)
    return md5.hexdigest(), sha.hexdigest() if sha else None


def verify_binary(
    item: DriveItem, path: Path, cancel=None
) -> tuple[bool, str, str | None, str]:
    if not path.is_file():
        return False, "missing", None, "local file is missing"
    if path.stat().st_size != item.size:
        return False, "size_mismatch", None, "local size differs from Drive"
    md5, sha = checksums(path)
    if not item.md5:
        return False, "unverifiable", sha, "Drive MD5 is absent; retain source"
    return (
        md5.lower() == item.md5.lower(),
        "verified" if md5.lower() == item.md5.lower() else "md5_mismatch",
        sha,
        "validated" if md5.lower() == item.md5.lower() else "MD5 differs from Drive",
    )
