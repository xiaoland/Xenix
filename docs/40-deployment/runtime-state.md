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

- `config/locale.json`
- `state/xenix.db`
- `artifacts/models/`
- `artifacts/training/`
- `artifacts/inference/`
- `artifacts/ml-tasks/<ml-task-id>/`

## Inspect

1. Start the app with `pdm run dev`.
2. Read the resolved paths from the main window.
3. Open the log directory from the UI or inspect files directly on disk.
4. Inspect `config/locale.json` for the persisted UI language preference when debugging localization behavior.
5. Inspect `state/xenix.db` for metadata, `artifacts/ml-tasks/` for per-ML-task working directories, and `artifacts/models/<work-item-id>/` for canonical trained-model files.

## Reset

1. Stop the app.
2. Delete only the runtime directory you intend to reset under `XENIX_APP_HOME`.
3. Restart the app so bootstrap recreates `config/`, `logs/`, `cache/`, `state/`, `temp/`, and `artifacts/`.

Do not store canonical datasets inside the runtime directory. Dataset registration keeps source files external.

Dataset import and dataset inspection do not use app-managed temp dataset copies. Import reads the user-managed source file directly and persists only dataset registration metadata plus work-item dataset-selection state in SQLite.

Issue `#72` adds ML task working directories with this shape:

- `artifacts/ml-tasks/<ml-task-id>/request.json`
- `artifacts/ml-tasks/<ml-task-id>/result.json`
- `artifacts/ml-tasks/<ml-task-id>/logs.jsonl`
- `artifacts/ml-tasks/<ml-task-id>/input/`
- `artifacts/ml-tasks/<ml-task-id>/models/`

Canonical trained models are copied out of task-local working directories into:

- `artifacts/models/<work-item-id>/`

## Backup Guidance

- Back up `state/xenix.db` together with any app-managed model, inference, or ML task working directories you need to preserve.
- User-managed source datasets should be backed up by normal user filesystem practices, not by app reset flows.
