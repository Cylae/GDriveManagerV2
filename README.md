# GDrive Space Manager

A Python 3.11+ desktop application for inspecting Google Drive, downloading verified local copies, exporting Workspace documents, and moving confirmed binary files to Drive Trash.

## Install and run

```bash
git clone https://github.com/Cylae/GDriveManagerV2.git
cd GDriveManagerV2
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
python main.py
```

Tkinter must be available in your Python installation. On Debian/Ubuntu, install `python3-tk` with your package manager. On Windows, use a Python installation that includes Tcl/Tk.

## Configure Google access

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable **Google Drive API**.
3. Configure the OAuth consent screen and add your Google account as a test user if the application is in testing mode.
4. Create an OAuth client with application type **Desktop app**.
5. Copy its Client ID into **Settings** and save.
6. Choose a local destination, then click **Refresh** to authorize in your browser.

The application uses authorization codes with PKCE and a temporary loopback callback on `127.0.0.1`. Startup reads only the local inventory cache; it does not open a sign-in browser automatically. The requested Drive scope permits reading files and moving files to Trash.

See Google's [desktop OAuth documentation](https://developers.google.com/identity/protocols/oauth2/native-app) for consent policies, test-user restrictions, and token expiry behavior.

## File safety

- Binary files require the Drive file's **content size** and MD5 checksum. Storage quota usage is not substituted for content size.
- Existing local files are preserved. Completed files are published through an exclusive filesystem operation; collisions receive a numbered name when auto-rename is enabled.
- Partial downloads have a private name derived from both the Drive file ID and requested local name. Different Drive files with the same visible name cannot append to the same partial.
- Interrupted downloads resume using HTTP Range. A resumed response must describe the expected offset and total size. A complete partial is verified without issuing a range beyond end-of-file.
- Cancellation interrupts retry waits, transfers, and checksum calculation. A cancellation observed before confirmation or the final trash request prevents that request.
- **Trash selected** downloads or verifies each binary, asks for confirmation, verifies the local copy again, and fetches current Drive metadata before moving it to Trash.
- Workspace documents and folders are **never** moved to Trash by this workflow. Workspace exports cannot be compared with a Drive content MD5.
- The application does not permanently delete Drive files or empty Drive Trash.

A remote metadata check and a later trash request are separate API operations. They do not provide a transaction against another application changing the same Drive file concurrently. The application also cannot prevent another local process from editing a verified destination. Keep these limits in mind when using actively edited files.

## Downloads and exports

**Download selected** verifies binary files and exports supported Workspace documents:

| Workspace type | Format |
| --- | --- |
| Document | DOCX |
| Spreadsheet | XLSX |
| Presentation | PPTX |
| Drawing | PNG |
| Other native types | PDF request; Google may reject unsupported types |

Exports are limited to 10 MiB by default and preserve meaningful dotted names, for example `report.v2.docx`. They retain the source on Drive.

The UI supports a searchable inventory, sorting, largest-file overview, transfer progress, queue CSV, inventory CSV, and a text session report. CSV exports escape spreadsheet formula prefixes in untrusted text. A single foreground operation runs at a time; settings cannot change during a transfer. All Tkinter access and confirmation dialogs stay on the UI thread.

## Credentials and local data

Application data lives in `~/.gdrive-space-manager/`:

- `config.json`: settings without refresh tokens; legacy refresh tokens migrate automatically.
- `inventory_cache.json`: a versioned inventory cache with a one-hour default lifetime.
- `operations.jsonl` and `operations.log`: session logs, rotated at the configured size threshold.
- Credentials: Windows DPAPI files, or the system keyring on macOS/Linux.

If the system keyring is unavailable, Unix platforms use a private file with mode `0600`. That fallback is **Base64 encoded, not encrypted**. Use an available system keyring when at-rest encryption is required. Writes use exclusive temporary files, flush and sync data, close descriptors before replacement, and clean up on failure.

OAuth refresh and interactive sign-in are serialized across workers. Logout waits for an active refresh, clears cached tokens, deletes the persisted refresh token, and removes the inventory cache. Network outages are reported instead of launching another sign-in browser.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q gdsm tests main.py
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
python -m mypy gdsm
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
```

The development tool versions are pinned. Mypy also checks bodies of unannotated functions. Tests isolate credentials and use fake network responses; they do not authorize an account or trash real Drive data.

To run the real Tkinter smoke tests with a display on Linux:

```bash
GDSM_GUI_TESTS=1 xvfb-run -a python -m unittest discover -s tests/integration -v
```

The environment flag is also supported on Windows/macOS with a graphical session. Native Windows DPAPI checks run only on Windows. GitHub Actions covers Python 3.11–3.13 on Linux and Python 3.12 on Windows and macOS, with a separate Linux Tkinter smoke step.

## Structure

- `gdsm/domain`: Drive items and validated settings.
- `gdsm/services`: OAuth, Drive API, transfer, verification, exports, cache, and logging.
- `gdsm/storage`: settings and credential persistence.
- `gdsm/ui`: Tkinter controllers, dialogs, and session view models. Worker methods perform blocking service calls; they communicate with widgets through an event queue.
- `gdsm/utils`: paths, exclusive file publication, retries, and CSV safety.
- `tests`: unit tests and optional graphical integration checks.

See [branch integration decisions](docs/BRANCH_INTEGRATION.md) and the [source branch manifest](docs/branch-integration.json) for the October 2026 consolidation.

## Current limits

Shared Drives are not explicitly enabled or validated. The language setting is retained for compatibility; the current interface labels are English. Theme changes apply on restart. Live Google account integration requires manual validation with a configured Desktop OAuth client; mocked tests cannot prove a specific account's consent configuration.
