# TP-00 — Managed AMD Durable Decision

## Outcome

Record the long-lived cross-unit contract before implementation. Managed AMD is a
new application-owned installation lifecycle under ADR 0007, not an extension of
ADR 0005's batch SSH worker pool. The design decisions are resolved in this
packet; this task records them in their durable owners.

## Owned Mutation

- add `docs/20-product-tdd/adr/0010-managed-amd-rocm-deployments.md`;
- update `docs/20-product-tdd/adr/README.md`;
- update `docs/20-product-tdd/storage-ownership.md`;
- add the managed-runtime/recovery route to `docs/40-deployment/README.md`.

No product source or task-local spike is changed.

## Contract to Lock

- desktop SQLite owns installation identity, immutable placement, desired
  presence, and component-generation lifecycle;
- component manifests own exact technical descriptors;
- Local/SSH sessions own target realization and live facts only;
- capability settings owners own managed provider projections and selection;
- live binding data is memory-only;
- Local and Private SSH are peer placements; changing placement creates a new
  installation;
- no CPU, placement, or external-API fallback;
- controller/target ownership, credential references, authentication, cache
  ownership, and cleanup authorization are explicit;
- v1 Private SSH uses OpenSSH public-key authentication through an explicit opaque
  credential reference and isolated pinned host trust; password, TOFU, implicit
  global agent/config fallback, and changed-host-key continuation are unsupported;
- an AMD-private enrolled-target record owns host/user/port, pinned host-key
  identity, and an explicit local identity-file reference; the installation stores
  only that immutable target ID, and private-key bytes are never copied into Xenix;
- every runtime incarnation requires authenticated loopback service access; an
  engine that cannot accept a protected secret handoff and reject unauthenticated
  requests is not admitted;
- forward-only reconcile, generation-specific provider IDs, and no aggregate
  `READY`;
- AMD is a removable composition slice under
  [the hard cut-off contract](../hard-cutoff.md); released migrations remain inert
  compatibility history and generic product code never depends on AMD.

## Acceptance

- the authority ledger has no duplicated mutable fact;
- ADR 0005 and existing ML worker code remain unchanged;
- Local, SSH, Dedicated Model API, and ordinary provider concepts are
  unambiguous;
- every durable/run-time/cache/projection fact has one owner;
- the durable contract includes the N-to-N+1 decommission sequence and old
  managed-ref/SQLite compatibility semantics;
- all document links and ADR index rows resolve.

## Verification

- documentation link check used by `pdm run check`;
- task diff review proving no code/schema mutation.
