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
- `config/ml_workers.json`
- `state/xenix.db`
- `artifacts/datasets/`
- `artifacts/datasets/transformed/`
- `artifacts/models/`
- `artifacts/reports/`
- `artifacts/apply/`
- `artifacts/apply/datasets/`
- `artifacts/ml-tasks/<ml-task-id>/`

## Inspect

1. Start the app with `pdm run dev`.
2. Read the resolved paths from the main window.
3. Open the log directory from the UI or inspect files directly on disk.
4. Inspect `config/locale.json` for the persisted UI language preference when debugging localization behavior.
5. Inspect `config/agent_settings.json` for persisted LLM providers, configured model lists, default/guard/title model keys, and development AIMock settings.
6. Inspect `config/ml_workers.json` for configured local and SSH ML workers. SSH credentials are not stored there; the file stores connection metadata, remote roots, Python command paths, and last setup/validation summaries.
7. Inspect `state/xenix.db` for metadata, `artifacts/datasets/` for app-managed dataset artifacts, `artifacts/ml-tasks/` for per-ML-task working directories, and `artifacts/models/` for canonical trained-model files.

## Reset

1. Stop the app.
2. Delete only the runtime directory you intend to reset under `XENIX_APP_HOME`.
3. Restart the app so bootstrap recreates `config/`, `logs/`, `cache/`, `state/`, `temp/`, and `artifacts/`.

Keep canonical source datasets outside the runtime directory. Dataset registration keeps source files external.

Dataset import and dataset inspection read the user-managed source file directly. Agent Harness and data services register app-managed dataset artifacts when data tools produce derived files. `data.query` returns bounded tool-result payloads by default; `data.transform` writes transformed CSV artifacts under `artifacts/datasets/transformed/`.

Current SQLite development baseline is `user_version=13`. Application startup runs forward migrations from supported earlier baselines. If a local development database belongs to an obsolete schema baseline, delete `state/xenix.db` under the active runtime home and restart the app so bootstrap recreates the current AI-first schema.

When a migration fails during development:

1. Stop the app.
2. Confirm the active runtime home and inspect `state/xenix.db`.
3. Check `PRAGMA user_version` and the affected table rows directly.
4. Fix app-owned bad persisted values with a new forward-only data migration. Do not mask known bad SQLite rows with tolerant ORM reads.
5. Re-run bootstrap or `pdm run smoke` against the same runtime home.

Agent Message kind and UI author are stored as SQLAlchemy enum member names in SQLite, for example `SYSTEM`, `USER`, and `ASSISTANT`. Agent Message lifecycle status is stored as lowercase enum values, for example `in_progress`, `completed`, `failed`, and `cancelled`.

Provider request usage records are stored in `agent_provider_request`. Each row records one primary or guard LLM provider request, input/output Message ids, provider/model metadata, request status, and normalized token usage when the provider reports it. The first hidden system prompt is stored as a system row in `agent_message` on the first turn and remains hidden from the Chatbot timeline.

Per-thread next-turn model selection is stored on `agent_thread.selected_fq_model_key`. The global default and configured model list live in `config/agent_settings.json`; if a thread has no selected key, runtime code falls back to the current global default.

ML worker pool configuration lives in `config/ml_workers.json`. The default configuration contains a local worker. SSH workers can be added through Settings; the setup wizard may create clearly marked `Host xenix.*` entries in the user's OpenSSH config, initializes remote execution directories, and validates a key/agent-based SSH connection. Remote worker directories are execution/cache state. Local SQLite metadata and local service-managed artifacts remain the final authority.

ML task type, ML task status, and ML task artifact kind are stored as lowercase enum values in SQLite, for example `fit`, `hyperparameter_tuning`, `apply`, `pending`, `succeeded`, and `apply_result`. Historical `INFERENCE` task values are migrated to `apply`; historical inspect-dataset task rows are removed because dataset inspection is runtime-derived and is not an ML task.

Turn completion guard audit decisions are stored in `agent_turn_completion_guard`. The corresponding retry reminder is stored as a normal system row in `agent_message`, because it is part of provider-facing conversation history.

Issue `#72` adds ML task working directories with this shape:

- `artifacts/ml-tasks/<ml-task-id>/request.json`
- `artifacts/ml-tasks/<ml-task-id>/result.json`
- `artifacts/ml-tasks/<ml-task-id>/logs.jsonl`
- `artifacts/ml-tasks/<ml-task-id>/input/`
- `artifacts/ml-tasks/<ml-task-id>/models/`

Canonical trained models are registered as artifacts under:

- `artifacts/models/`

Issue `#94` adds optional SSH worker execution. Remote task directories mirror local task working directories during execution, but result paths are downloaded and rewritten to local task paths before `MLTaskService` finalizes success.

## Backup Guidance

- Back up `state/xenix.db` together with any app-managed dataset artifacts, model artifacts, apply outputs, reports, or ML task working directories you need to preserve.
- User-managed source datasets should be backed up by normal user filesystem practices, not by app reset flows.
