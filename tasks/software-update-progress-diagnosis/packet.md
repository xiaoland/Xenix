# Software Update Progress and About Version

## Objective

Add a dedicated modeless software-update download-progress surface and show the
installed application version in About.

## Guardrails

- User approval was received on 2026-07-26 for the modeless progress surface and
  About version display.
- Preserve unrelated working-tree changes.
- Keep update state authoritative in `UpdateService`; the dialog only projects its
  progress callback.
- Keep download and apply explicitly user-confirmed.
- Do not add a cancel action without a service-level cancellation contract.
- Closing About or Settings must not hide or cancel an active download.
- Preserve update admission, pre-apply backup, updater handoff, and restart behavior.

## Verification

- About displays the canonical `APP_VERSION`.
- Confirmed downloads create one visible `Qt.NonModal` 0–100 progress dialog.
- Worker-thread progress reaches the GUI only through a Qt signal.
- Closing About leaves the progress dialog visible; completion or failure closes and
  disposes it.
- English and Simplified Chinese labels remain complete.
- Focused UI, service, and i18n tests plus repository checks pass.

## Current Truth

- About displays the canonical `APP_VERSION` before the build commit.
- About emits update intent; Settings forwards it; the MainWindow-owned
  `SoftwareUpdateController` is the sole UI lifecycle owner for automatic checks,
  manual checks, downloads, apply handoff, and the progress window.
- Confirmed downloads display one 0–100 `Qt.NonModal` `QProgressDialog`. A queued
  Qt signal projects the service callback onto the GUI thread.
- Closing About or Settings leaves the progress window visible. Completion,
  failure, or MainWindow closure closes and disposes it.
- Automatic and manual checks share one operation gate. Repeated intent cannot
  start a concurrent check or download.
- English and Simplified Chinese catalogs contain 388 finished translations each.
- The PRD now owns the installed-version and modeless download-progress promise.
- Approved state diff:
  - From: no installed-version row and a silent background download represented
    only by a disabled button.
  - To: canonical installed version in About and a dedicated, determinate,
    modeless download-progress window that survives closing About or Settings.
- Blast radius: About UI, its parent ownership wiring, Qt translations, focused UI
  tests, and the PRD capability statement. Update-service, release, storage, and
  updater semantics remain unchanged.
- Verification:
  - Focused update/UI/i18n selection: 5 passed.
  - `test_update_service.py`, `test_settings_dialog.py`, and `test_i18n.py`:
    14 passed.
  - All 60 `test_main.py` nodes passed in bounded batches. One earlier combined
    process experienced a non-reproducible Python 3.14 native import crash; the
    implicated existing test passed alone and in its batch.
  - `pdm run check` and `git diff --check` pass.

## Next Step

Hand the verified implementation to the user; commit only on an explicit command.
