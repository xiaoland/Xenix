# Startup Database Recovery Execution

## Objective & Hypothesis

Add a startup recovery path for local SQLite bootstrap failure. If `state/xenix.db` cannot initialize, the app should let the user quarantine the database and retry bootstrap instead of requiring manual AppData deletion.

Hypothesis: keeping migrations strict while moving user-confirmed recovery into `app.py` preserves storage ownership and prevents accidental deletion of unrelated runtime state.

## Guardrails Touched

- Startup UI owns the recovery dialog and retry flow.
- Storage migrations remain forward-only and strict.
- Recovery must not delete `config/`, `logs/`, `artifacts/`, or the whole runtime home.
- Recovery should rename the failed database to a timestamped backup path, not permanently delete it.
- User-visible strings must go through Qt translation extraction/compile.

## Verification

- `pdm run pytest tests\test_main.py::test_quarantine_database_renames_with_timestamp_and_collision_suffix tests\test_main.py::test_main_window_can_quarantine_failed_startup_database_and_rebuild tests\test_migrations.py tests\test_storage_bootstrap.py -q` passed with 19 tests.
- `pdm run i18n-extract` found 7 new startup recovery strings.
- `pdm run i18n-compile` passed; `xenix_zh_CN.qm` generated 206 finished translations and 0 unfinished translations.
- `pdm run check` passed.
- `pdm run pytest tests\test_main.py::test_quarantine_database_renames_with_timestamp_and_collision_suffix tests\test_main.py::test_main_window_can_quarantine_failed_startup_database_and_rebuild tests\test_migrations.py tests\test_storage_bootstrap.py tests\test_i18n.py -q` passed with 24 tests.
