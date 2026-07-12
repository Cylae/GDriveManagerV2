from __future__ import annotations
import re
import shutil
from pathlib import Path

_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_name(value: str, max_len: int = 180) -> str:
    if not value:
        return "_"
    result = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(". ")
    if not result:
        result = "_"
    if Path(result).stem.upper() in _RESERVED:
        result = "_" + result
    suffix = Path(result).suffix
    if len(result) > max_len:
        result = result[: max_len - len(suffix)].rstrip(". ") + suffix
    return result


def safe_target(root: str, relative: str) -> Path:
    raw_parts = [p for p in re.split(r"[\\/]+", relative) if p]
    if any(p in (".", "..") for p in raw_parts):
        raise ValueError("path traversal blocked")
    base = Path(root).resolve()
    parts = [safe_name(p) for p in raw_parts]
    if not parts:
        raise ValueError("empty or unsafe relative path")
    target = (base.joinpath(*parts)).resolve()
    if base != target and base not in target.parents:
        raise ValueError("path traversal blocked")
    if len(str(target)) > 240:
        raise ValueError("target path exceeds safe Windows limit")
    return target


def unique_target(path: Path, auto_rename: bool = True) -> Path:
    if not path.exists():
        return path
    if not auto_rename:
        raise FileExistsError(str(path))
    for n in range(1, 10000):
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError("no available target name")


def ensure_space(directory: Path, needed: int, reserve: int) -> None:
    free = shutil.disk_usage(directory).free
    if free < needed + reserve:
        raise OSError(
            f"insufficient disk space: {free} available, {needed + reserve} required"
        )
