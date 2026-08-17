# Settings Dialog Open Latency

**Status:** implementation and automated verification complete; manual visual
acceptance remains

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

- [x] Trace every synchronous operation before the dialog becomes visible.
- [x] Time the real `QPushButton.click -> MainWindow._open_settings ->
  SettingsDialog.show` path against an isolated copy of the development runtime.
- [x] Prove the dialog becomes visible while a deliberately blocked index-status
  read is still running, then renders the completed result on the GUI thread.
- [x] Prove repeated refresh triggers remain single-flight and lifecycle-fenced.
- [x] Run the repository's live headed benchmark through real provider paths.
- [x] Scan persisted benchmark reports for credential- or endpoint-shaped content.
- [x] Run the focused regression, `pdm run test`, `pdm run check`, and `pdm run
  smoke`.
- [ ] Confirm on the ordinary visible desktop that the first MainWindow Settings
  click paints immediately and changes from checking to the final index state.

## Current Truth

- The pre-repair root cause was `SettingsDialog` performing a deep LanceDB
  generation validation synchronously on the Qt GUI thread before first paint,
  then repeating the same status query in `showEvent`.
- Settings document reads and AMD composition are not material contributors.
- `SettingsDialog` now renders only cached UI state and owns one
  lifecycle-fenced request bridge. `KnowledgeIndexService` owns a single-query
  executor independently of its serialized rebuild worker, so query and
  mutation cannot starve one another through one FIFO.
- An active text-vector task receives a fast `building` projection without
  competing for the vector lifecycle lock. Idle status reads and successful
  rebuild publication retain the physical generation-integrity validation.
- Against an isolated copy of the real 67-unit runtime on the final architecture,
  dialog construction took `0.034272 s`, `show()` returned in `0.002908 s`, and
  the actual `2.573765 s` deep validation completed on the service query lane.
  A prior cold run of the same deep operation took `6.829751 s`; neither duration
  is paid by the GUI thread.
- Two live headed cases completed with semantic and integrity passes. The
  Judge-required case also passed its Judge.
- A final post-repair repetition reached the real provider path but all three
  attempts were rejected with `llm_provider_http_429`; they are recorded as
  external runtime errors, not acceptance passes or semantic failures.
- The pre-existing worktree was committed as `d2fb5a4` and `2ed78f0` before the
  repair began.
- The focused regression passes `7 / 7`; the full manifest passes `51 / 51`;
  `pdm run check` and `pdm run smoke` pass; both translation catalogs contain
  `420 / 420` finished messages.

See [diagnosis evidence](evidence/diagnosis.md) and
[headed benchmark evidence](evidence/headed-benchmark.md). The implementation
and timing proof is in [repair evidence](evidence/repair.md).

## Next Step

Perform the one remaining manual visual acceptance from MainWindow. No product
or architecture decision remains open for this repair.
