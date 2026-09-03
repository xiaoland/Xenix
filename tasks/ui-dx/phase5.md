# Phase 5 — Conversation seam rehearsal

## Admitted design

Extract a pure `ConversationTurnController` that owns the selected Thread,
submission generation, pending append acknowledgement, active sampling, and
pause/closed gates. It classifies Harness events into bounded UI decisions;
it does not construct Qt objects, read paths, project canonical Messages, or
duplicate the Harness execution lifecycle. MainWindow remains the adapter for
rendering, localization, attachment path lookup, history, and model selection.

Implementation proceeds through two cohesive batches: state/gating first,
execution dispatch and a narrow view integration next. Constructor reduction
belongs primarily to Phase 6; a service bag is not an intermediate design.

## Transition rehearsal

| Input | Decision / invariant |
| --- | --- |
| Submit while idle | Capture generation + attachment count; gate duplicate submit |
| Matching nonfinal snapshot | Acknowledge Composer once; canonical append is irreversible |
| Failure before acknowledgement | Preserve retryable Composer input |
| Failure after acknowledgement | Reproject stable snapshot; never restore submitted input |
| Old-generation event or failure | Ignore, including same-Thread re-entry |
| Stop before sampling is known | Return localized preparing-state outcome; no pause call |
| Successful Thread pause | Ignore live updates but admit matching final snapshot |
| Final snapshot | Clear local pending/generation and converge on canonical projection |
| Select/create Thread | Invalidate old UI generation; unlock Composer without resending |
| Accepted window close | Reject queued UI updates; do not claim to cancel service I/O |

Attachment paths stay in MainWindow's transient adapter mapping. The pure state
only retains attachment count and returns a validated source index. The unused
cancelled-pending set is removed: it has no writers and adds no real gate.

## Discovered defects to cover while moving the boundary

- History selection currently clears active generation but not pending Composer,
  leaving future submit permanently gated after old callbacks are discarded.
- Worker failures currently carry no generation, so an old failure can reset a
  newer submission. The Qt failure bridge must carry the originating generation.
- Closing a still-valid QWidget does not reject queued UI events. A closed gate
  protects the UI; service/DB shutdown quiescence remains a separate runtime issue.
- Headed benchmark settlement reads removed private state. Replace only those
  observations with a small public idle query, without changing benchmark cases,
  provider limits, or canonical outcome checks.
- A final snapshot can follow append acknowledgement without a live sampling
  event. Final rendering must also exit Composer preparation, not just clear
  its running flag.

## Verification

Use a small pure transition portfolio plus real `ThreadDetailView` composer
contracts (pre-append abort and post-append acknowledgement). Then exercise a
provider-free MainWindow adapter with a controlled executor, run the existing
Harness first slice, benchmark offline checks/discovery, full tests, static
checks, native UI smoke, and an isolated production smoke before accepting the
integrated slice. No live-provider test is authorized or needed.

## Implemented evidence

- `conversation/turn_controller.py` owns the pure turn gates and returns bounded
  action/acknowledgement/index decisions. It stores neither paths nor message text.
- `conversation/execution.py` provides a typed, injected stream executor.
  Production `app.py` composes it from the existing Harness stream callable;
  the MainWindow fixture substitutes a manually driven executor.
- MainWindow no longer owns the pending/active/paused state machine or starts
  submission threads itself. Its adapter retains only transient attachment path
  lookup, projection, localized messages, and QWidget updates.
- Headed settlement uses public selected-Thread/idle observations; the Harness
  measurement signals and canonical outcomes remain intact.
- 14 focused pure/execution/MainWindow contracts pass in 4.13s (7.29s runner
  wall time). Full portfolio: 189 passed in 149.39s. Strict checking passes for
  32 boundary modules; `pdm run check` passes.
- Native Windows smoke: 1 passed. Benchmark offline checks: 33 passed. Headed
  discovery: 13 cases, with no provider calls. Production smoke passes using a
  unique temporary `XENIX_APP_HOME` and disabled OTLP; that synthetic home was
  removed after successful exit.
- Rehearsal failures produced four synthetic MainWindow artifact manifests,
  screenshots, Qt logs, and an aggregate index under ignored `ui-artifacts/`.
  These are retained debugging evidence, not current test failures or baselines.

The executor intentionally does not join or force-cancel I/O during close.
Service/DB quiescence during an already-admitted operation is not a guarantee
introduced by this UI slice and remains a runtime lifecycle concern.
