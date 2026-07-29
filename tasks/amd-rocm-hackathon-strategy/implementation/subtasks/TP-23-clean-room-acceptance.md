# TP-23 — Clean-room Lifecycle Acceptance

## Outcome

Execute the complete [clean-room lifecycle
matrix](../clean-room-acceptance.md) for both Private SSH and Local Linux Radeon
roles, then publish redacted evidence supporting only the claims actually proven.

## Owned Mutation

- add/extend task-local acceptance harnesses and redacted evidence;
- add durable tests only for reproducible lifecycle regressions discovered here;
- update deployment runbooks for proven recovery/cleanup behavior.

This task does not change release workflows, submit the contest entry, delete the
feasibility lab, terminate a cloud instance/PVC, or publish credentials without
separate authorization.

## Preconditions

- fresh instance/PVC or attested clean image for each role;
- fresh client runtime and isolated SSH trust/credential state;
- product/cache roots absent and ambient caches redirected;
- TP-19, TP-21, and TP-22 verification green;
- exact target capacity/retention and artifact sources available.

## Required Runs

- cold install and cold self-test timing;
- warm idempotent reconcile;
- interrupted acquisition and exact-manifest repair;
- app/service/SSH/target restart and stale-controller fencing;
- G2 resource-blocked upgrade with G1 untouched;
- retire with selected/default/reference and in-flight Chat/Embedding/OCR blockers;
- cleanup attestation and explicit reinstall to a new identity;
- full OCR → Embedding → LLM Tool → local Artifact journey.

Every phase is repeated with deterministic failpoints where practical. Current
operations fail without semantic replay, and only later operations rematerialize.

## Acceptance

- both placement matrices pass independently;
- before/after filesystem/process/listener/forward/settings/SQLite inventories show
  exact ownership and cleanup;
- cold/warm labels and measurements are honest;
- unauthenticated requests and non-ROCm fallbacks fail;
- provider settings and diagnostic/evidence scans contain no dynamic endpoint,
  token, host secret, private key, live PID, or user content;
- evidence chain is complete from package/commit through cleanup;
- TP-24's AMD-absent subprocess/package proof passes with old inert AMD SQLite rows
  and managed refs typed unavailable without fallback;
- released-feature acceptance includes release-N retirement/cleanup attestation
  before the release-N+1 source cut; a direct pre-release cut proves no
  installation/projection/live realization ever existed;
- unproven native Windows/Linux desktop claims remain absent.

## Verification

- all focused lifecycle/capability tests;
- full repository test/check/smoke/package manifest;
- redacted evidence/link/whitespace/secret scan;
- manual review of the exact claims matrix.
