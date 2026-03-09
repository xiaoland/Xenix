# Runtime State Runbook

## Purpose

Explain where local runtime state lives and how to inspect or reset it during development.

## Location

Runtime state is rooted at:

- `XENIX_APP_HOME` when the environment variable is set
- Otherwise the platform default returned by `xenix.config.get_app_paths()`

Current runtime directories:

- `config/`
- `logs/`
- `cache/`

## Inspect

1. Start the app with `pdm run dev`.
2. Read the resolved paths from the main window.
3. Open the log directory from the UI or inspect files directly on disk.

## Reset

1. Stop the app.
2. Delete only the runtime directory you intend to reset under `XENIX_APP_HOME`.
3. Restart the app so bootstrap recreates `config/`, `logs/`, and `cache/`.

Do not store canonical datasets inside the runtime directory unless a future contract explicitly says they are app-managed copies.

## Backup Guidance

- Back up SQLite metadata once it exists together with any app-managed model or result directories.
- User-managed source datasets should be backed up by normal user filesystem practices, not by app reset flows.
