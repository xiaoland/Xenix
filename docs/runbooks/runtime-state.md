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
- `state/`
- `temp/`
- `artifacts/`

Current runtime files and subdirectories:

- `state/xenix.db`
- `temp/datasets/`
- `artifacts/models/`
- `artifacts/training/`
- `artifacts/inference/`
- `artifacts/ml-tasks/<ml-task-id>/`

## Inspect

1. Start the app with `pdm run dev`.
2. Read the resolved paths from the main window.
3. Open the log directory from the UI or inspect files directly on disk.
4. Inspect `state/xenix.db` for metadata and `artifacts/ml-tasks/` for per-task working directories once ML task execution exists.

## Reset

1. Stop the app.
2. Delete only the runtime directory you intend to reset under `XENIX_APP_HOME`.
3. Restart the app so bootstrap recreates `config/`, `logs/`, `cache/`, `state/`, `temp/`, and `artifacts/`.

Do not store canonical datasets inside the runtime directory. Dataset registration keeps source files external. Services may create temporary dataset copies under `temp/datasets/` during execution and remove them after use.

## Backup Guidance

- Back up `state/xenix.db` together with any app-managed model, inference, or ML task working directories you need to preserve.
- User-managed source datasets should be backed up by normal user filesystem practices, not by app reset flows.
