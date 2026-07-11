# GDrive Space Manager — project_v0.2

Release artifact: `project_v0.2.zip`

A dependency-free Python 3.11+ desktop application for Windows, Linux and macOS. It uses Tkinter, the Python standard library, Google OAuth 2.0 Authorization Code + PKCE, and Google Drive API v3.

## Safety guarantees implemented

- Binary Drive files are moved to Trash **only after** an explicit user confirmation and a local size + Drive MD5 validation.
- Existing local files are never overwritten; names are disambiguated.
- Interrupted binary downloads use `.gdsm.partial` files and HTTP Range resumption.
- Google Workspace files are export-only. They are never auto-trashed because a comparable Drive MD5 is unavailable.
- Tokens are stored in an OS-user-local configuration file with restrictive permissions where supported. For stronger Windows secret protection, replace `JsonStore` token persistence with Credential Manager/DPAPI before enterprise deployment.

## Install and run

```bash
python -m unittest discover -s tests -v
python main.py
```

No third-party package is required. Create a **Desktop** OAuth client in Google Cloud, enable Google Drive API, then paste its Client ID in Settings.

## Limitations deliberately visible

- This is a practical v2.0 desktop baseline, not an enterprise identity product. It does not use Windows Credential Manager/DPAPI because it intentionally has no external dependencies.
- The built-in UI is functional but intentionally conservative; it does not claim a full visual analytics dashboard.
- Shared Drive support requires enabling it in the API query and adding tests with a real Shared Drive account.
