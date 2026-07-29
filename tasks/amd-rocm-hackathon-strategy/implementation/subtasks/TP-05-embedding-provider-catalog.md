# TP-05 — Embedding Provider Catalog

## Outcome

Migrate Embedding from one static provider document to a capability-owned
multi-instance catalog with an explicit active provider and a resource-free
configuration snapshot.

## Owned Mutation

- modify `src/xenix/services/embedding_service.py`;
- add `src/xenix/services/embedding_settings.py` and
  `src/xenix/services/embedding_provider_factory.py`, with compatibility re-exports
  from `embedding_service.py`;
- modify `src/xenix/services/knowledge_index_service.py` only for the changed
  profile/selection contract;
- add/extend Embedding settings, service, batch, migration, and Knowledge rebuild
  confirmation tests.

UI and AMD files are not edited.

## Data and Ports

- schema v1 single provider migrates to schema v2 provider catalog plus active
  instance through TP-03;
- explicit `StaticEmbeddingTarget | ManagedEmbeddingProviderRef`; the managed ref
  has an opaque `manager_id` and no AMD type;
- typed user and managed-projection commands;
- app-scoped explicit factory registry with no import-time or entry-point
  discovery;
- `freeze()` snapshots configuration/profile only;
- each `embed_texts()` enters one operation scope across all batches.

## Vector Identity

Static-provider compatibility remains stable across the structural migration.
Managed fingerprint uses exact model/tokenizer/component generation/manifest
identity. It excludes base URL, forward port, placement, runtime incarnation, and
aggregate profile revision. BGE-M3 stores `dimensions=None`, omits the request
field, and observes 1024 during self-test/response validation.

## Acceptance

- v1 files migrate without losing secrets or unexpectedly invalidating existing
  static indexes;
- stale UI/background CAS is explicit and rebuild confirmation is recomputed;
- G2 ensure does not change active G1;
- active exact provider blocks removal;
- later-batch dispatched disconnect returns no partial batch, performs no semantic
  retry/switch, and publishes no vector generation;
- one multi-batch call enters/exits exactly one generation scope.
- an unknown/removed manager loads as typed unavailable without dispatch,
  selection change, fallback, or index publication;
- explicit active-provider change is one command: switch and immediately rebuild,
  or cancel. v1 does not admit “switch now, rebuild later”; failed rebuild leaves
  semantic retrieval unavailable rather than using the old vector generation.

## Verification

- focused migration/settings/service/index tests;
- multi-batch disconnect black-box fixture;
- `pdm run check`.
