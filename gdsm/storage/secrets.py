import sys


def save_secret(key: str, value: str) -> None:
    if sys.platform == "win32":
        _save_win32(key, value)
    else:
        _save_keyring(key, value)


def load_secret(key: str) -> str | None:
    if sys.platform == "win32":
        return _load_win32(key)
    else:
        return _load_keyring(key)


def delete_secret(key: str) -> None:
    if sys.platform == "win32":
        _delete_win32(key)
    else:
        _delete_keyring(key)


# macOS / Linux Fallback using keyring
def _save_keyring(key: str, value: str) -> None:
    try:
        import keyring  # type: ignore
        keyring.set_password("GDriveSpaceManager", key, value)
    except Exception:
        # Document explicit fallback per instructions if keyring fails or is not available
        import os
        import base64

        d = os.path.expanduser("~/.gdrive-space-manager")
        os.makedirs(d, exist_ok=True)
        fallback_path = os.path.join(d, f".{key}.secret")

        import tempfile
        fd, tmp = tempfile.mkstemp(dir=d, prefix=f".{key}-", text=False)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(base64.b64encode(value.encode()).decode())
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, fallback_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def _load_keyring(key: str) -> str | None:
    try:
        import keyring  # type: ignore
        return keyring.get_password("GDriveSpaceManager", key)
    except Exception:
        import os
        import base64

        d = os.path.expanduser("~/.gdrive-space-manager")
        os.makedirs(d, exist_ok=True)
        fallback_path = os.path.join(d, f".{key}.secret")
        if os.path.exists(fallback_path):
            try:
                with open(fallback_path, "r", encoding="utf-8") as f:
                    return base64.b64decode(f.read().encode()).decode()
            except Exception:
                return None
        return None


def _delete_keyring(key: str) -> None:
    try:
        import keyring  # type: ignore
        keyring.delete_password("GDriveSpaceManager", key)
    except Exception:
        pass
    import os

    d = os.path.expanduser("~/.gdrive-space-manager")
    os.makedirs(d, exist_ok=True)
    fallback_path = os.path.join(d, f".{key}.secret")
    if os.path.exists(fallback_path):
        os.remove(fallback_path)


# Windows DPAPI implementation using ctypes
def _save_win32(key: str, value: str) -> None:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    CryptProtectData = getattr(ctypes, "windll").crypt32.CryptProtectData
    LocalFree = getattr(ctypes, "windll").kernel32.LocalFree

    data_in = DATA_BLOB()
    encoded = value.encode("utf-8")
    data_in.cbData = len(encoded)
    data_in.pbData = ctypes.cast(
        ctypes.c_char_p(encoded), ctypes.POINTER(ctypes.c_char)
    )

    data_out = DATA_BLOB()

    if CryptProtectData(
        ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)
    ):
        try:
            encrypted_data = ctypes.string_at(data_out.pbData, data_out.cbData)
            import os

            path = os.path.expanduser(f"~/.gdrive-space-manager/.{key}.dpapi")
            import tempfile
            d = os.path.dirname(path)
            os.makedirs(d, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=d, prefix=f".{key}-", text=False)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(encrypted_data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        finally:
            LocalFree(data_out.pbData)


def _load_win32(key: str) -> str | None:
    import os

    path = os.path.expanduser(f"~/.gdrive-space-manager/.{key}.dpapi")
    if not os.path.exists(path):
        return None

    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    CryptUnprotectData = getattr(ctypes, "windll").crypt32.CryptUnprotectData
    LocalFree = getattr(ctypes, "windll").kernel32.LocalFree

    with open(path, "rb") as f:
        encrypted_data = f.read()

    data_in = DATA_BLOB()
    data_in.cbData = len(encrypted_data)
    data_in.pbData = ctypes.cast(
        ctypes.c_char_p(encrypted_data), ctypes.POINTER(ctypes.c_char)
    )

    data_out = DATA_BLOB()

    if CryptUnprotectData(
        ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)
    ):
        try:
            decrypted_data = ctypes.string_at(data_out.pbData, data_out.cbData)
            return decrypted_data.decode("utf-8")
        finally:
            LocalFree(data_out.pbData)
    return None


def _delete_win32(key: str) -> None:
    import os

    path = os.path.expanduser(f"~/.gdrive-space-manager/.{key}.dpapi")
    if os.path.exists(path):
        os.remove(path)
