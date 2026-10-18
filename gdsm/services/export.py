from __future__ import annotations

import os
import tempfile
import urllib.error
import urllib.parse
from pathlib import Path

from ..domain.models import DriveItem
from ..utils.files import publish_new_file
from .drive_api import DriveApi

MIME_TO_EXT = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}


def export_workspace_file(
    api: DriveApi,
    item: DriveItem,
    target: Path,
    max_bytes: int = 10 * 1024 * 1024,
    *,
    cancel=None,
    auto_rename: bool = True,
) -> tuple[str, str, str]:
    """Export without overwriting existing files; exports never authorize trash."""
    if cancel is not None and cancel.is_set():
        raise InterruptedError("cancelled")
    if not item.is_native or item.is_folder:
        return "skipped", str(target), "Not a Google Workspace file"
    export_mime, extension = MIME_TO_EXT.get(
        item.mime_type, ("application/pdf", ".pdf")
    )
    # Append to the Drive name rather than discarding a meaningful dotted suffix.
    if not target.name.lower().endswith(extension):
        target = target.with_name(target.name + extension)
    url = (
        f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(item.id, safe='')}/export"
        f"?mimeType={urllib.parse.quote(export_mime, safe='')}"
    )
    try:
        with api._request(url, cancel=cancel) as response:
            size = response.headers.get("Content-Length")
            if size and int(size) > max_bytes:
                return "error", str(target), "Export exceeds size limit"
            content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                return (
                    "error",
                    str(target),
                    "Export exceeds size limit (no Content-Length)",
                )
        if cancel is not None and cancel.is_set():
            raise InterruptedError("cancelled")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".export-", dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            if cancel is not None and cancel.is_set():
                raise InterruptedError("cancelled")
            final = publish_new_file(temporary, target, auto_rename)
        finally:
            temporary.unlink(missing_ok=True)
        return (
            "exported_unverifiable",
            str(final),
            "Workspace export cannot be checksum-verified; retain source",
        )
    except InterruptedError:
        raise
    except urllib.error.HTTPError as error:
        try:
            if error.code == 403:
                body = error.read().decode("utf-8", errors="ignore").lower()
                if "exceeds" in body or "too large" in body:
                    return "error", str(target), "Export exceeds Google size limit"
            return "error", str(target), f"HTTP Error {error.code}: {error.reason}"
        finally:
            error.close()
    except (OSError, ValueError) as error:
        return "error", str(target), str(error)
