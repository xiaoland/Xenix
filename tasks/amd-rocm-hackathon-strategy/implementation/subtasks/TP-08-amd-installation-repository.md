# TP-08 — AMD Installation Repository

## Outcome

Create the sole durable desired-state authority for managed AMD installations and
component generations in SQLite.

## Owned Mutation

- modify `src/xenix/services/storage/models.py`;
- add the implementation-time current-version → next-version edge in
  `src/xenix/services/storage/migrations.py`;
- add `src/xenix/services/storage/repositories/amd_installations.py`;
- update repository exports;
- add migration/bootstrap/repository tests.

No target process, endpoint, PID, port, health, tunnel, permit, or cache state is
stored here.

Released migration edges and primitive AMD table models are inert compatibility
history after hard cut-off. `storage.models`, bootstrap, and migrations may not
import an AMD service enum/type or require the AMD package to exist. Core tables
have no foreign key to AMD tables.

## Minimum Model

- private target enrollment: target ID, host/user/port, pinned host-key identity,
  and explicit local identity-file reference; no private-key bytes;
- installation ID, immutable tagged placement/opaque target reference, immutable
  resolved profile, and desired presence;
- component generation ID, capability, manifest digest, materialization
  lifecycle, phase/error, and bounded immutable verification/attestation
  reference;
- generation-specific lifecycle transitions supporting G1/G2 coexistence;
- optimistic version/transition guard needed by one coordinator.

The schema must not persist aggregate `READY`; registration and live availability
are queried from their owners.

## Invariants

- placement cannot mutate after installation creation;
- target enrollment referenced by an installation cannot be retargeted; changed
  address, user, port, host key, or credential reference creates a new target and
  installation;
- generation identity and manifest digest never change;
- technical descriptor changes create a new generation;
- `RETIRING`/desired absence never returns to normal reconcile;
- target-side manifests are observations, not normative generation records;
- forward migration only; never edit an already released migration edge.

## Acceptance

- fresh bootstrap and previous-version upgrade both pass;
- model/repository round-trip and invalid transition cases pass;
- G1 and G2 coexist without key reuse;
- restart reconstructs desired lifecycle exactly;
- bounded attestation rejects secrets/live endpoint/process fields;
- repository tests remain independent of SSH, Local processes, and settings.
- an old-AMD database initializes and migrates with the AMD module absent, without
  reading, writing, or dropping inert AMD rows.

## Verification

- focused migration/bootstrap/repository tests;
- storage invariant/type checks;
- `pdm run check`.
