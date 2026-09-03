# Real CI artifact acceptance

## Authorized route

The user explicitly approved a task-specific `feat/ui-dx -> main` draft PR,
without merging. PR: https://github.com/xiaoland/Xenix/pull/124.
Only committed feature work was pushed; the unrelated local README and
worker-pool changes remain uncommitted. Neither main nor develop was changed.

## Acceptance checks

- Inspect actual GitHub job and step conclusions, not only local workflow syntax.
- Download the named `pytest` and `ui-artifacts` archives.
- Verify the root index and all five scenario manifests, actual PNGs and tree JSON.
- Confirm synthetic policy, declared viewport, Windows runner/QPA/style/locale and
  resolved text font. Inspect representative images, including the black user
  message bubble and provider/OCR controls.
- Distinguish positive-run capture evidence from failure-path upload evidence;
  do not claim the latter from `if: always()` syntax alone.

## Runs

- Initial run: https://github.com/xiaoland/Xenix/actions/runs/33351291911
  Commit: `ae40bd5e7162371b0c5bc6ed7cd88972fb301302`.
  **Success**, job duration 9m20s. Static checks, full portfolio, five scene
  captures, Windows native smoke, index construction and both uploads succeeded.

## Downloaded evidence

Local root: `ui-artifacts/ci-downloads/33351291911/` (ignored; synthetic only).

- `pytest` artifact id `9743849056`, archive 6,377 bytes. Downloaded JUnit:
  208 tests, 0 errors, 0 failures, 0 skipped, 266.967 seconds.
- `ui-artifacts` artifact id `9743849466`, archive 92,959 bytes. Index count 5;
  all five sets contain valid `manifest.json`, `tree.json`, `actual.png`.
- Every declared file length matches its downloaded file. Every tree has both
  ownership and layout relations. All manifests use synthetic policy.
- Runner: Windows Server 2022 build 20348, Python 3.14.2, PySide/Qt 6.11.1,
  offscreen, Fusion, en_US, DPI 96, DPR 1. Requested/resolved font: Segoe UI
  Regular 9pt, exact match true.
- Viewports: chat.empty 900x680; chat.mixed-timeline 900x720;
  chat.running-with-attachments 900x680; history 248x680; Settings 1050x760.
- Downloaded mixed-chat and Settings screenshots visually inspected: text is
  legible, controls present, black user-message bubble intact, no icon-font
  fallback or square glyphs. Native smoke passed separately in 2.35s.

## Acceptance boundary

The positive real-CI artifact path is accepted. The three expected-failure
subprocess tests also passed in CI, demonstrating failure capture inside tests.
However, their temporary artifacts are not in the uploaded archive, and the
overall job did not fail. **Whole-job failure followed by always-upload remains
unverified**; Phase 4 must not be marked wholly complete on this run alone.
No pixel baseline/diff authority is admitted by a single successful run.
