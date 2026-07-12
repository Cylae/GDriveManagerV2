from __future__ import annotations
import urllib.request
import urllib.error
from pathlib import Path
from ..domain.models import DriveItem
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
    api: DriveApi, item: DriveItem, target: Path, max_bytes: int = 10 * 1024 * 1024
) -> tuple[str, str, str]:
    if not item.is_native:
        return "skipped", str(target), "Not a Google Workspace file"

    export_mime, ext = MIME_TO_EXT.get(item.mime_type, ("application/pdf", ".pdf"))
    target = target.with_suffix(ext)

    url = f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(item.id, safe='')}/export?mimeType={urllib.parse.quote(export_mime, safe='')}"

    try:
        with api._request(url) as response:
            size_str = response.headers.get("Content-Length")
            if size_str and int(size_str) > max_bytes:
                return "error", str(target), "Export exceeds size limit"

            content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                return (
                    "error",
                    str(target),
                    "Export exceeds size limit (no Content-Length)",
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            return (
                "exported_unverifiable",
                str(target),
                "Workspace export cannot be checksum-verified",
            )
    except urllib.error.HTTPError as e:
        if e.code == 403:
            # Check if it's a size limit error from google
            body = e.read().decode("utf-8", errors="ignore")
            if "exceeds" in body.lower() or "too large" in body.lower():
                return "error", str(target), "Export exceeds Google size limit"
        return "error", str(target), f"HTTP Error {e.code}: {e.reason}"
    except Exception as e:
        return "error", str(target), str(e)
