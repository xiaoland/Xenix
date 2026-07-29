# Settings Dialog Open Latency

## Objective

Eliminate the several-second first-open freeze in `MainWindow` Settings without
weakening Knowledge index integrity, and prove both the Settings interaction and
the ordinary headed product journey complete end to end.

## Guardrails

- Commit the already-completed AMD and repository work before changing product
  code for this repair.
- Keep `KnowledgeIndexService` authoritative for index state; the dialog owns
  only an asynchronous UI projection.
- Do not weaken or bypass physical vector-generation integrity checks.
- A hidden, closed, or shut-down dialog must not accept stale task results or
  start another refresh.
- Separate measured facts from environment-dependent inference.
- Do not persist provider credentials or raw benchmark evidence.
- Treat headed benchmark execution, integrity, semantics, and Judge status as
  independent result channels.

## Verification

- Trace every synchronous operation before the dialog becomes visible.
- Time the real `QPushButton.click -> MainWindow._open_settings ->
  SettingsDialog.show` path against an isolated copy of the development runtime.
- Prove the dialog becomes visible while a deliberately blocked index-status
  read is still running, then renders the completed result on the GUI thread.
- Prove repeated refresh triggers remain single-flight and lifecycle-fenced.
- Run the repository's live headed benchmark through real provider paths.
- Scan persisted benchmark reports for credential- or endpoint-shaped content.
- Run the focused regression, `pdm run test`, `pdm run check`, and `pdm run
  smoke`.

## Current Truth

- Root cause is diagnosed: `SettingsDialog` performs a deep LanceDB generation
  validation synchronously on the Qt GUI thread before first paint, then repeats
  the same status query in `showEvent`.
- Settings document reads and AMD composition are not material contributors.
- Two live headed cases completed with semantic and integrity passes. The
  Judge-required case also passed its Judge.
- Sir authorized implementation after the pre-existing worktree is committed
  into at most two reviewable commits.
- The pre-repair baseline passes all 45 manifest tests, `pdm run check`, and
  `pdm run smoke`.
- Product code has not yet changed for this repair.

See [diagnosis evidence](evidence/diagnosis.md) and
[headed benchmark evidence](evidence/headed-benchmark.md).

## Next Step

Commit the pre-existing worktree, then implement a UI-owned single-flight
background refresh with cached rendering and lifecycle-fenced completion.
