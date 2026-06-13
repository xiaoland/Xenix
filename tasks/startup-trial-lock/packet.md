## Objective & Hypothesis

Add a build-configurable startup lock for small-scope test builds. When the packaged trial duration is greater than zero and the locally recorded first-run date is older than the allowed day count, startup should stop before the main workbench opens and tell the user to buy/download the licensed build at `https://lanzhijiang.dev/xenix`.

## Guardrails Touched

- Intent owner: `docs/10-prd/product-scope.md` should gain the product claim before implementation.
- Runtime owner: startup orchestration in `src/xenix/app.py`.
- State owner: local runtime state under `AppPaths.state` or `AppPaths.config`, with one authority for first-run timestamp.
- UI/i18n owner: startup dialog strings use `QCoreApplication.translate("XenixStartup", ...)` and translation catalogs must be refreshed if implemented.

## Verification

- Unit coverage for disabled env value `0` and unset env value.
- Unit coverage for first run creating trial state and allowing startup.
- Unit coverage for unexpired and expired windows using deterministic clock injection.
- Startup integration coverage proving expired interactive startup shows a blocking prompt and does not construct/show `MainWindow`.
- Smoke behavior should remain usable when the trial lock is disabled.

## Current Understanding

- `src/xenix/app.py` already owns startup orchestration, splash lifecycle, translated startup message boxes, logging, storage bootstrap, and main window construction.
- `src/xenix/config.py` owns runtime directory resolution and `XENIX_APP_HOME`.
- Existing app directories include `state/`, which is the strongest fit for machine-local first-run state.
- This version intentionally does not include license activation, so the lock should be a one-way startup gate rather than a license service.

## Candidate Shape

- Build-time environment variable name: likely `XENIX_TRIAL_LOCK_DAYS`.
- Packaging should embed the resolved value in a generated module, similar to `_generated_trial_llm.py`; runtime environment variables should not be consulted for this policy.
- `0`, unset, or blank should disable. Invalid values should fail packaging instead of producing an ambiguous build.
- Persist first-run timestamp in a small JSON file such as `state/trial_lock.json`.
- The state file can be tamper-evident with a keyed HMAC/signature derived from a packaged build secret, but it cannot be made tamper-proof on a machine controlled by the user.
- Check after `ensure_app_dirs(paths)` and translation initialization, before expensive runtime imports/storage/main window construction.
- On expired interactive startup, close splash, show a blocking dialog with a button that opens `https://lanzhijiang.dev/xenix`, then exit with code `1`.
- On expired smoke/non-interactive startup, raise a typed exception so tests and packaging checks can detect the policy without hanging on a dialog.

## Open Decisions

- Whether "N days" means calendar date difference or exact elapsed 24-hour windows.
- Whether users should be able to continue on the exact expiry day until midnight or lock immediately after the elapsed threshold.
- Whether the dialog should include an "Exit" button only, or "Buy license" plus "Exit".
- How much tamper resistance is worth the complexity for a small-scope test build.

## Next Step

Implementation completed for the local test-build startup lock. Review the final diff and decide whether to package a trial build with `XENIX_TRIAL_LOCK_DAYS`.

## Verification Results

- `pdm run pytest tests\test_trial_lock.py tests\test_build_info.py`
- `pdm run pytest tests\test_trial_lock.py tests\test_build_info.py tests\test_main.py -k "trial or smoke_test_bootstraps_runtime_in_fresh_app_home"`
- `pdm run pytest tests\test_i18n.py -k startup`
- `pdm run check`
- `pdm run smoke`

## Follow-up Fix

- Added build-time `XENIX_TRIAL_LOCK_STATE_SECRET` so all builds in one 60-day test wave can share the same state signing secret. When the variable is absent and the lock is enabled, packaging still generates a per-build random secret.
- Trial lock dialogs now always include the lock `reason`, expiry value or `-`, and state file path in detailed text, including `tampered` and `clock_rollback` cases.

Verification:

- `pdm run i18n-compile`
- `pdm run pytest tests\test_build_info.py tests\test_main.py -k "trial_lock or trial"`
- `pdm run pytest tests\test_trial_lock.py`
- `pdm run check`
