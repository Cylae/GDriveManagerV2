# GDrive Space Manager v0.3

- **Date**: July 2024
- **Python Version Used**: 3.12.13

## Features Added
- Fully refactored codebase into a clean, layered architecture (`domain/`, `services/`, `storage/`, `ui/`, `utils/`).
- **Secret Storage (§1)**: OAuth refresh tokens are now securely stored using Windows DPAPI or macOS/Linux `keyring` (with encrypted file fallback), removed from plaintext config. Old config files automatically migrate.
- **Trash Safety (§2)**: Trash operations now enforce strict verification: files must be successfully downloaded, match Drive's size, match Drive's MD5 checksum, move atomically, and receive explicit user confirmation (Yes / Yes to all).
- **Workspace Export (§3)**: Native Workspace documents are now exported gracefully with appropriate MIME-to-extension mappings (.docx, .xlsx, .pptx, .png, .pdf fallbacks) while respecting Google's size limits. Workspace files are never queued for auto-trash.
- **Drive Path Resolution (§4)**: Implemented full Drive Path resolution resolving nested folders, handling orphaned files smoothly, preventing cycle loops via max-depth checks, and seamlessly determining shortcut targets.
- **User Interface (§5)**: Modernized the Tkinter UI with a settings dialog (Concurrency, Retries, Language, Space reserve configuration), sortable columns, and a responsive debounced search (300ms). Added live updating progress bars and ETA analytics powered by a thread-safe event loop.
- **Concurrency & Cancellation (§6)**: Enhanced threading so that long-running network operations (download, inventory) can be accurately interrupted via a `threading.Event` cancellation token without triggering false trash calls.
- **HTTP Reliability (§7)**: Built an advanced retry decorator applying bounded exponential backoff with jitter and parsing `Retry-After` headers for seamless recovery from 408, 425, 429, and 500+ series errors, plus 403 quota-exceeded handling.
- **Inventory Cache (§8)**: Added a robust local `.cache.json` caching mechanism for Drive API inventories featuring atomic writes, version mismatches tracking, and TTL checking to enable instant UI loading when refreshed via cache.
- **Logging & Exports (§9-10)**: Implemented dual logging combining human-readable `.log` output with structural `.jsonl` data. Added reliable log rotation based on byte thresholds. The UI now supports exporting transfer queues and rich text session reports alongside CSV item dumps (UTF-8 BOM supported).

## Bugs Fixed
- Missing OAuth refresh token injection correctly patched to ensure headless persistence.
- Shortcut resolutions accurately implemented fetching API `shortcutDetails`.
- Thread-safe event queue unpacking correctly configured across cache and live network fetches avoiding UI freezes.

## Known Limitations
- Export formats for Workspace files are limited to CSV functionality inside the application unless extended dependencies are integrated.
- Only CSV queue exports and simple Session report `.txt` files are supported; XLSX exporting is absent to maintain a dependency-free core footprint outside of the `keyring` library requirement.
- UI elements like progress bars require accurate HTTP Content-Length headers, failing which indeterminate progress loading may be displayed.

## Migration Notes
- First v0.3 launch automatically rewrites `config.json` extracting and clearing the `refresh_token` to migrate to your native OS secure credential store.

## Test Results
- **29 unit tests passed successfully** via Python's native `unittest` suite (Covering paths, cycles, caching limits, exports, network timeouts, secrets masking).
- **Compilation Check**: `python -m compileall -q .` - Clean.
- **Lint Check**: `ruff check .` - Clean.
- **Type Check**: `mypy gdsm` - Clean.
