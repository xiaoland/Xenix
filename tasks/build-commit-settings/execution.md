# Execution Task

## Objective & Hypothesis

- Objective: Show the packaged git commit in Settings as an embedded build string.
- Hypothesis: A generated module created by the packaging script can carry the commit into the PyInstaller bundle while normal runtime code reads only constants.

## Pre-Execution Restatement

- Target: Settings runtime information and PyInstaller packaging path.
- Current state and context: Settings shows runtime paths and logs, but no source build identity. Packaging compiles translations and then runs PyInstaller from `xenix.spec`.
- Operation: Add a small build-info module with a development fallback, generate `_generated_build_info.py` before packaging, and display the commit in Settings.
- Scope included: `src/xenix/build_info.py`, `src/xenix/ui/settings_dialog.py`, `scripts/package_app.py`, `.gitignore`, tests, and translations.
- Scope excluded: Database state, app startup git calls, version metadata redesign, and installer metadata.
- Invariants: Runtime code must not call git; Settings remains service-driven and only displays a string; development runs remain usable without generated build info.
- Likely affected files: Settings dialog layout and translation resources.
- Uncertainty: Whether all local translation `.qm` files are current before this change.

## Guardrails Touched

- UI layer text must support `retranslate_ui()`.
- Packaging truth must be injected at build time, not discovered at packaged-app runtime.

## Plan

1. Add build info boundary with development fallback.
2. Generate/remove embedded build info during packaging.
3. Display build commit in Settings runtime card.
4. Add focused tests and refresh translations.

## Verification

- Command: `pdm run pytest tests/test_build_info.py tests/test_main.py::test_main_window_keeps_settings_entry_on_thread_detail_view_shell tests/test_i18n.py::test_main_window_language_switch_updates_chat_shell`
- Expected: Build-info helpers, Settings display, and Settings label translation pass.
- Observed: Passed: 6 tests. Pytest emitted a Windows temp symlink cleanup permission warning after completion.
- Command: `pdm run check`
- Expected: Source, tests, and scripts compile.
- Observed: Passed.
- Command: Confirm `src/xenix/_generated_build_info.py` is absent after checks.
- Expected: Generated build-info file is not left in the source tree.
- Observed: Absent.

## Promotion Notes

- Durable truth candidates: Build identity is carried by `xenix.build_info` and packaging-generated `_generated_build_info.py`.
- Keep in task only: Implementation trace and verification results.
