"""Durable settings writes and publication without overwriting user files."""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from pathlib import Path


def atomic_write(path: Path, data: bytes, prefix: str = ".gdsm-") -> None:
    """Replace an application-owned file after closing its private temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=prefix, dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_new_file(source: Path, target: Path, auto_rename: bool = True) -> Path:
    """Publish a completed file using an exclusive filesystem operation.

    Hard links provide atomic publication on NTFS and POSIX filesystems. On
    filesystems without hard links, an exclusive copy still prevents overwrites.
    A failed copy removes only the file created by this operation.
    """
    for index in range(10000):
        candidate = (
            target
            if index == 0
            else target.with_name(f"{target.stem} ({index}){target.suffix}")
        )
        try:
            try:
                os.link(source, candidate)
            except OSError as error:
                if error.errno not in (
                    errno.EXDEV,
                    errno.EPERM,
                    errno.ENOSYS,
                    errno.ENOTSUP,
                    errno.EINVAL,
                ):
                    raise
                # Opening exclusively also rejects dangling destination symlinks.
                with candidate.open("xb") as output:
                    try:
                        with source.open("rb") as incoming:
                            shutil.copyfileobj(incoming, output, length=1024 * 1024)
                        output.flush()
                        os.fsync(output.fileno())
                    except BaseException:
                        output.close()
                        candidate.unlink(missing_ok=True)
                        raise
        except FileExistsError:
            if not auto_rename:
                raise
            continue
        source.unlink()
        return candidate
    raise FileExistsError("no available target name")
