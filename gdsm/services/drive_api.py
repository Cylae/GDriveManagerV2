from __future__ import annotations
import json
import urllib.parse
import urllib.request
from ..domain.models import DriveItem
from ..utils.retry import with_retry
from .cache import InventoryCache
from pathlib import Path
import os
from .oauth import GoogleOAuth


class DriveApi:
    def __init__(self, oauth: GoogleOAuth):
        self.oauth = oauth
        self.items_by_id: dict[str, DriveItem] = {}
        self._path_memo: dict[str, str] = {}
        self.oauth = oauth

    @with_retry()
    def _request(self, url, method="GET", body=None, headers=None):
        h = {"Authorization": "Bearer " + self.oauth.token(), **(headers or {})}
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        return urllib.request.urlopen(req, timeout=60)

    def inventory(self, cancel=None, force_refresh=False):
        cache = InventoryCache(
            Path(os.path.expanduser("~/.gdrive-space-manager/inventory_cache.json"))
        )
        cached_items = cache.load()
        if cached_items is not None and not force_refresh:
            self.items_by_id = {i.id: i for i in cached_items}
            return cached_items, "cached"

        all_items = self._fetch_all_items(cancel)
        self.items_by_id = {i.id: i for i in all_items}
        for i in all_items:
            i.drive_path = self.resolve_path(i.id)
        cache.save(all_items)
        return all_items, "live"

    def _fetch_all_items(self, cancel=None):
        all_items = []
        page = None
        fields = "nextPageToken,files(id,name,mimeType,size,quotaBytesUsed,md5Checksum,modifiedTime,parents,owners(displayName),capabilities(canDownload,canTrash),shortcutDetails(targetId))"
        while True:
            q = {
                "pageSize": "1000",
                "q": "trashed = false",
                "orderBy": "quotaBytesUsed desc",
                "fields": fields,
            }
            if cancel and cancel.is_set():
                raise InterruptedError("cancelled")
            if page:
                q["pageToken"] = page
            with self._request(
                "https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(q)
            ) as r:
                data = json.load(r)
            for x in data.get("files", []):
                mime = x["mimeType"]
                caps = x.get("capabilities", {})
                raw = x.get("quotaBytesUsed", x.get("size", "0"))
                try:
                    size = int(raw)
                except (ValueError, TypeError):
                    size = 0
                owners = x.get("owners", [])
                owner = owners[0].get("displayName", "") if owners else ""
                shortcut_target = ""
                if (
                    mime == "application/vnd.google-apps.shortcut"
                    and "shortcutDetails" in x
                ):
                    shortcut_target = x["shortcutDetails"].get("targetId", "")
                item = DriveItem(
                    x["id"],
                    x["name"],
                    mime,
                    size,
                    x.get("md5Checksum"),
                    x.get("modifiedTime", ""),
                    owner,
                    tuple(x.get("parents", [])),
                    bool(caps.get("canDownload")),
                    bool(caps.get("canTrash")),
                    mime == "application/vnd.google-apps.folder",
                    mime.startswith("application/vnd.google-apps.")
                    and mime != "application/vnd.google-apps.folder",
                    "",
                    shortcut_target,
                )
                all_items.append(item)
            page = data.get("nextPageToken")
            if not page:
                return all_items

    def binary_url(self, item):
        return (
            "https://www.googleapis.com/drive/v3/files/"
            + urllib.parse.quote(item.id, safe="")
            + "?alt=media"
        )

    def download_request(self, item, offset=0):
        h = {"Authorization": "Bearer " + self.oauth.token()}
        if offset:
            h["Range"] = f"bytes={offset}-"
        return urllib.request.Request(self.binary_url(item), headers=h)

    def trash(self, item):
        data = b'{"trashed":true}'
        headers = {"Content-Type": "application/json"}
        with self._request(
            "https://www.googleapis.com/drive/v3/files/"
            + urllib.parse.quote(item.id, safe=""),
            method="PATCH",
            body=data,
            headers=headers,
        ):
            pass

    def resolve_path(self, item_id: str, depth: int = 0) -> str:
        if item_id in self._path_memo:
            return self._path_memo[item_id]
        if depth > 100:
            return "<cycle-detected>"
        if item_id not in self.items_by_id:
            return "<orphaned>"

        item = self.items_by_id[item_id]

        # Resolve shortcuts
        target_id = getattr(item, "shortcut_target", None)
        if target_id:
            res = self.resolve_path(target_id, depth + 1)
            self._path_memo[item_id] = f"{res} (shortcut)"
            return self._path_memo[item_id]

        if not item.parents:
            self._path_memo[item_id] = f"/{item.name}"
            return self._path_memo[item_id]

        parent_id = item.parents[0]
        parent_path = self.resolve_path(parent_id, depth + 1)
        self._path_memo[item_id] = f"{parent_path}/{item.name}"
        return self._path_memo[item_id]
