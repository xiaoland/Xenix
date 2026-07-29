# TP-20A — Guided AMD Install Contract Repair

**Status:** delivered; automated, headed validation, SSH failure-path, and both
package modes passed. One fresh operational UI lifecycle remains for human
acceptance.

## Trigger

On the Windows debug build, pressing `Install` could fail immediately with no
visible reason even when the user believed all required fields were complete.
The runtime had no SSH security document, target row, installation row, or AMD
log event, proving that the failure happened before target I/O. The catch-all
worker discarded the rejected field and exception type, while the UI rendered
only raw lifecycle codes and treated any returned status as success.

This is not a missing Save button. `Install` is the single user-approved
enrollment plus deployment command.

## Architecture Repair

```text
AmdGuidedSetupDialog
  -> synchronous validate_private_fields         pure syntax, no I/O/write
  -> AmdDeploymentTaskRunner                     scheduling + safe projection
  -> AmdGuidedDeploymentService.install_private  one application command
       -> full validation                         identity check in worker
       -> SQLite target + installation ensure    discoverable command identity
       -> SettingsStore security record          exact-idempotent checkpoint
       -> AmdAiDeploymentService.reconcile        forward only
```

Ownership:

- Qt owns collection, field focus, localization, and presentation only.
- `AmdGuidedDeploymentService` owns the cross-authority application command.
- `AmdSshSecurityStore` remains the sole owner of local SSH security handles.
- the AMD installation repository remains the sole target/installation lifecycle
  owner.
- placement/session code owns target I/O and emits only typed safe error codes.
- capability settings owners still own LLM, Embedding, and OCR provider
  registration; no selection changes.

There is no compensation delete or rollback journal. SQLite commits first so a
process restart can rediscover the exact hidden installation/target IDs even if
SettingsStore security publication did not finish. An exact retry keeps any
completed monotonic checkpoint and continues forward. A reused immutable ID with
different facts fails as a typed conflict.

## Product/UI Contract

- Current product topology is Windows Xenix to Private SSH Linux Radeon. Local
  Linux is not offered as a desktop product placement; its controller is
  composed cleanup-only so historical generations retain an exact owner.
- Normal users enter host, SSH user/port, identity file, and a verified server
  host key. Internal installation/target IDs are generated and hidden.
- A reopened dialog discovers every non-removed durable installation. When more
  than one exists, a stable dialog-local selector manages each identity without
  exposing or asking users for internal IDs. A retirement-only build likewise
  discovers all Local and Private history.
- Security drafts belong only to the selected installation and are cleared on
  selection changes. Cached operation/Remove results are updated per identity,
  so switching cannot replay stale state or revive a retiring installation.
- Pure syntax validation runs synchronously. Filesystem availability and the full
  authoritative check run in the worker, then return the exact invalid field to
  focus with a localized message and stable support code.
- A host-key line must be a complete algorithm-plus-blob public key, optionally
  with a comment, or an exact endpoint-matching un-hashed `known_hosts` line.
  Fingerprints, private keys, login-key instructions, mismatch, multi-line input,
  and malformed/algorithm-mismatched blobs are rejected.
- Install/Repair succeeds only when all three components are operational.
  Incompatible, degraded, installing, and not-materialized states are failures
  with a durable-installation-available flag that truthfully controls Repair and
  Remove.
- Target observation failures are separate from compatibility evidence. A target
  that resets or cannot be reached is `not_materialized`/`degraded` with its SSH
  error code; only measured profile constraint failures are `incompatible`.
- Logs contain only operation/result flags, condition, phase, stable error code,
  safe field/security-checkpoint metadata, and exceptional class name. They
  exclude endpoint, user, port, identity path, host key, SSH output, request
  repr, raw exception text, and traceback.
- Remove projects actual `removed`, `retiring`, or `removal_blocked` state;
  `already_removed` is never shown as active cleanup. Remove is the latest user
  intent, so an older Install/Repair completion cannot overwrite its outcome.
- Durable availability is tri-state. An unreadable status never collapses to
  absence or discards a retryable identity; SQLite desired presence/lifecycle
  remains authoritative even when profile or SSH-security reads also fail.
- Close cannot hide an active command. App shutdown fences late UI delivery
  without claiming to cancel already committed remote work.

## Owned Mutation

- add `src/xenix/services/amd/guided.py`;
- modify AMD composition, deployment idempotency/status projection, SSH error
  typing/security parsing, guided worker, guided dialog, and the bounded app
  composition call;
- update AMD translation entries, ADR/runbook, and task evidence;
- add automated tests only after the production implementation is complete, per
  the task execution constraint.

No `services/ml/**`, ML Worker settings, generic LLM/Embedding/OCR/Knowledge
service, storage schema/migration, public endpoint resolver, or Save action is in
scope.

## Acceptance

- blank/invalid fields start no worker or durable write and focus the correct
  widget;
- a fully valid form sends exactly one guided command;
- strict host-key parsing covers OpenSSH public-key and exact known-hosts forms;
- checkpoint retries converge and immutable conflicts do not overwrite state;
- restart after either cross-authority checkpoint restores the same hidden IDs;
- operational alone projects success; all partial/incompatible states remain
  readable failures with correct Repair/Remove availability;
- SSH client/trust/auth/timeout/connection failures stay distinct through the UI;
- AMD log/diagnostic evidence is useful and contains none of the prohibited
  values;
- feature-off source/package smoke remains AMD-free, preserving a quick hard
  cut-off;
- the real debug dialog and a fresh Radeon Cloud Private SSH lifecycle are walked
  end to end after automated verification.

## Completed Evidence

- focused guided/AMD regressions: `59 passed`;
- full manifest: `104 passed`;
- translation extraction/compilation: `525 / 525` finished in each catalog;
- `pdm run check`, source smoke, default package/smoke, and AMD cut-off
  package/forced-enable smoke passed;
- headed production dialog proved no Save/Local action, read-only field
  validation, exact focus, one guided command, typed real SSH failure,
  truthful Repair/Remove availability, restart recovery, and log redaction;
- Radeon Cloud remained TCP-reachable but reset SSH key exchange, so no remote
  mutation was attempted in this repair acceptance.

The redacted screenshots, structured log, and JSON assertions are in
[`guided-ui-headed-2026-07-29`](../../evidence/guided-ui-headed-2026-07-29/README.md).

## Remaining Human Acceptance

On a restored or fresh Radeon Cloud target, use the visible dialog to reach
operational Chat, Embedding, and OCR and then Remove the installation. This is a
physical acceptance journey, not an unresolved architecture, implementation,
validation, error-model, observability, or packaging task.
