# TP-03 — Revisioned SettingsStore

## Outcome

Create one physical, app-lifetime JSON document writer with per-document revision,
compare-and-swap, crash-safe publication, and opaque notifications. It owns no LLM,
Embedding, OCR, UI, redaction, selection, or provider semantics.

## Owned Mutation

- add `src/xenix/services/settings_store.py`;
- add `tests/test_settings_store.py`.

This task does not migrate a capability schema, edit `app.py`, or absorb
`ml_workers.json`.

## Interface

- immutable `SettingsSnapshot(payload, revision)`;
- `load(document_id)`;
- `compare_and_swap(document_id, expected_revision, transform)`;
- idempotent canonical no-op result;
- opaque post-commit `(document_id, revision)` notification and
  `watch(after_revision)`-equivalent without a missed-update window;
- app-lifetime writer identity plus fail-closed second-process fencing.

The fence is a settings-root OS file lock implemented through a small injectable
standard-library Windows/POSIX adapter. It does not depend on the Windows-only app
single-instance guard or add a third-party locking dependency.

Legacy bare JSON is read as revision 0. Its first successful mutation atomically
publishes an envelope containing payload and monotonically increasing
per-document revision. A sidecar revision is rejected because payload and revision
would not be atomic.

## Invariants

- transform runs against the committed current payload under the document writer
  fence;
- stale expected revision is typed conflict and publishes nothing;
- temp-write/flush/replace failure leaves the previous document valid;
- event fires after durable publication and outside the writer lock;
- no-op changes create no revision or event;
- notifications carry no payload or secret;
- revisions are ordered only within one document, never globally.
- the store has no manager/AMD document ID, owner, event, error, or import.

## Acceptance

- legacy, fresh, stale-CAS, same-value, crash/failure, subscriber-race, concurrent
  thread, and second-process cases pass;
- unknown envelope/schema fails closed without overwriting;
- Windows and POSIX writer-fencing behavior has an executable test seam;
- store tests do not import LLM, Embedding, OCR, or UI.
- an AMD-module-absent subprocess runs the store and second-writer fence tests.

## Verification

- `pdm run pytest --direct tests/test_settings_store.py`;
- `pdm run check`.
