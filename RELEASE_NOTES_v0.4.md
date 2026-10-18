# GDrive Space Manager 0.4.0

Consolidation date: 2026-10-18.

- Reconcile the 86 divergent branches, retaining every source head in Git ancestry.
- Serialize OAuth refresh, browser authorization, and logout; avoid browser prompts on network outages and validate token lifetimes.
- Handle Retry-After seconds and HTTP dates with bounded, cancellable waits.
- Share durable private-file writes across settings, inventory cache, fallback credentials, and Windows DPAPI persistence.
- Close file descriptors before replacement and preserve previous files when replacement fails.
- Preserve local downloads and Workspace exports during name collisions, including concurrent downloads.
- Isolate partials by Drive identity, validate HTTP Range responses, and verify complete partials without an out-of-bounds resume request.
- Use Drive content size instead of quota bytes for content verification.
- Never trash Workspace documents or folders. Revalidate the local binary and current Drive metadata after user confirmation.
- Keep Tkinter calls on the UI thread, reuse OAuth state, and prevent overlapping foreground operations from resetting cancellation.
- Validate settings transactionally, improve CSV escaping, and serialize concurrent session log writes.
- Add pinned development tools and CI across Linux, Windows, and macOS.

Legacy partials named `*.gdsm.partial` are not automatically reused by the new identity-based partial naming. They are left untouched. Existing settings and credential filenames remain compatible.

The Unix file credential fallback is Base64 encoded with private file permissions, not encrypted. Older release notes overstated its protection; the README now describes it accurately.
