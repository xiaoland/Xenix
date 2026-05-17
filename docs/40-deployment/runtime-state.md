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
- `config/agent_settings.json`
- `state/xenix.db`
- `artifacts/datasets/`
- `artifacts/models/`
- `artifacts/reports/`
- `artifacts/predictions/`
- `artifacts/ml-tasks/<ml-task-id>/`

## Inspect

1. Start the app with `pdm run dev`.
2. Read the resolved paths from the main window.
3. Open the log directory from the UI or inspect files directly on disk.
4. Inspect `config/locale.json` for the persisted UI language preference when debugging localization behavior.
5. Inspect `config/agent_settings.json` for the persisted LLM provider and development AIMock settings.
6. Inspect `state/xenix.db` for metadata, `artifacts/datasets/` for app-managed dataset artifacts, `artifacts/ml-tasks/` for per-ML-task working directories, and `artifacts/models/` for canonical trained-model files.

## Reset

1. Stop the app.
2. Delete only the runtime directory you intend to reset under `XENIX_APP_HOME`.
3. Restart the app so bootstrap recreates `config/`, `logs/`, `cache/`, `state/`, `temp/`, and `artifacts/`.

Keep canonical source datasets outside the runtime directory. Dataset registration keeps source files external.

Dataset import and dataset inspection read the user-managed source file directly. Agent Harness and data services register app-managed dataset artifacts when data tools produce derived files.

Current SQLite development baseline is `user_version=2`. If a local development database belongs to an obsolete schema baseline, delete `state/xenix.db` under the active runtime home and restart the app so bootstrap recreates the current AI-first schema.

Issue `#72` adds ML task working directories with this shape:

- `artifacts/ml-tasks/<ml-task-id>/request.json`
- `artifacts/ml-tasks/<ml-task-id>/result.json`
- `artifacts/ml-tasks/<ml-task-id>/logs.jsonl`
- `artifacts/ml-tasks/<ml-task-id>/input/`
- `artifacts/ml-tasks/<ml-task-id>/models/`

Canonical trained models are registered as artifacts under:

- `artifacts/models/`

## Backup Guidance

- Back up `state/xenix.db` together with any app-managed dataset artifacts, model artifacts, prediction outputs, reports, or ML task working directories you need to preserve.
- User-managed source datasets should be backed up by normal user filesystem practices, not by app reset flows.
