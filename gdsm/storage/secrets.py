"""OS-backed credentials, with an explicit private-file fallback on Unix."""

from __future__ import annotations

import base64
import binascii
import ctypes
import logging
import re
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Any

from ..utils.files import atomic_write

_LOG = logging.getLogger(__name__)
_SERVICE = "GDriveSpaceManager"


def _secret_path(key: str, suffix: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise ValueError("invalid credential key")
    directory = Path.home() / ".gdrive-space-manager"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory / f".{key}.{suffix}"


def save_secret(key: str, value: str) -> None:
    """Save a credential, propagating failures instead of losing it silently."""
    if sys.platform == "win32":
        _save_win32(key, value)
    else:
        _save_keyring(key, value)


def load_secret(key: str) -> str | None:
    """Read a credential from the current platform's store."""
    return _load_win32(key) if sys.platform == "win32" else _load_keyring(key)


def delete_secret(key: str) -> None:
    """Remove a credential and any legacy fallback copy."""
    if sys.platform == "win32":
        _delete_win32(key)
    else:
        _delete_keyring(key)


def _save_keyring(key: str, value: str) -> None:
    path = _secret_path(key, "secret")
    try:
        import keyring

        keyring.set_password(_SERVICE, key, value)
    except Exception:  # noqa: BLE001 - third-party credential backends have varied failures
        # Base64 is only a compatibility encoding, NOT encryption.
        _LOG.warning(
            "System credential store unavailable; using a private, unencrypted fallback file"
        )
        atomic_write(path, base64.b64encode(value.encode("utf-8")), f".{key}-")
    else:
        path.unlink(missing_ok=True)


def _load_keyring(key: str) -> str | None:
    path = _secret_path(key, "secret")
    try:
        import keyring

        value = keyring.get_password(_SERVICE, key)
        if value is not None:
            return value
    except Exception:  # noqa: BLE001 - third-party credential backends have varied failures
        _LOG.debug("System credential store unavailable")
    try:
        return base64.b64decode(path.read_bytes(), validate=True).decode("utf-8")
    except (FileNotFoundError, ValueError, UnicodeError, binascii.Error):
        return None


def _delete_keyring(key: str) -> None:
    path = _secret_path(key, "secret")
    try:
        import keyring
    except ImportError:
        path.unlink(missing_ok=True)
        return
    try:
        value = keyring.get_password(_SERVICE, key)
    except keyring.errors.NoKeyringError:
        # No backend exists, so there cannot be a system-store copy to delete.
        pass
    except keyring.errors.KeyringError:
        # A backend that cannot be read cannot prove that deletion succeeded.
        raise
    else:
        if value is not None:
            keyring.delete_password(_SERVICE, key)
    path.unlink(missing_ok=True)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    """Call DPAPI with explicit pointer types, including on 64-bit Windows."""
    loader = getattr(ctypes, "WinDLL")  # noqa: B009 - unavailable in Linux type stubs
    crypt32 = loader("crypt32", use_last_error=True)
    kernel32 = loader("kernel32", use_last_error=True)
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    function.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    incoming = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    outgoing = _DataBlob()
    # CRYPTPROTECT_UI_FORBIDDEN prevents a hidden system dialog on worker threads.
    if not function(
        ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)
    ):
        error: Any = getattr(ctypes, "WinError")()  # noqa: B009 - Windows-only API
        raise error
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        kernel32.LocalFree(outgoing.pbData)


def _save_win32(key: str, value: str) -> None:
    path = _secret_path(key, "dpapi")
    encrypted = _dpapi(value.encode("utf-8"), protect=True)
    atomic_write(path, encrypted, f".{key}-")


def _load_win32(key: str) -> str | None:
    path = _secret_path(key, "dpapi")
    try:
        encrypted = path.read_bytes()
    except FileNotFoundError:
        return None
    return _dpapi(encrypted, protect=False).decode("utf-8")


def _delete_win32(key: str) -> None:
    _secret_path(key, "dpapi").unlink(missing_ok=True)
