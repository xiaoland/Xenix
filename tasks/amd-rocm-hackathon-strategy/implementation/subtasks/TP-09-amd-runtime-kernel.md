# TP-09 — AMD Runtime Kernel

## Outcome

Implement the private placement-neutral runtime primitives and prove concurrency,
retirement, fencing, and recovery with fake sessions before real GPU or SSH I/O.

## Owned Mutation

- add `src/xenix/services/amd/runtime.py`;
- add `src/xenix/services/amd/placement.py`;
- add `src/xenix/services/amd/AGENTS.md` locking the inward-only dependency,
  no-import-time-registration, and single-composition-anchor rules;
- add private package exports only where composition requires them;
- add `tests/test_amd_runtime.py`.

No capability settings, protocol parsing, deployment UI, or real placement driver
is added.

## Primitives

- `AmdExecutionSession` protocol;
- private multi-installation exact-reference runtime directory;
- memory-only `LoopbackHttpBinding`;
- per-generation admission gate and scoped permit;
- runtime incarnation and controller owner fencing;
- shutdown/orphan-drain contract and deterministic fake Local/SSH sessions.

There is no global “current AMD session.” The runtime directory is private to AMD
adapters and never returned from `AmdAiDeploymentService`.

## Retirement Linearization

While holding the exact gate lock, prevent new admissions, commit durable
`RETIRING` through TP-08, mark the gate closed, then release the lock. A failed
commit publishes no accepted retirement. A crash after commit destroys the
process, and restart rebuilds the gate closed from durable state.

Previously issued permits drain. After controller crash, an empty new-process
counter is not proof that old remote work ended; physical cleanup waits for the
placement orphan policy or terminates only a fully verified owned process.

## Acceptance

- two Local/SSH installations resolve independently by exact ref;
- retiring refuses new permits while existing permits drain;
- late callbacks, port reuse, and stale incarnation cannot publish/stop/delete a
  newer realization;
- binding loss fails the current scope without generation switch;
- restart from every lifecycle failpoint preserves forward direction;
- secret/live-binding values never enter persistence or public representation.
- removal of the AMD package requires no runtime-kernel edit outside the declared
  slice and bounded composition anchors.

## Verification

- deterministic concurrency/crash/fencing tests;
- `pdm run pytest --direct tests/test_amd_runtime.py`;
- `pdm run check`.
