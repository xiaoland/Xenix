# Storage Ownership

## Admission

Data, artifact, Agent, ML, and persistence units must agree on which store is
authoritative. Losing this contract can expose local paths, orphan canonical
outputs, or delete user-owned input.

## Authority

- SQLite owns bounded, queryable local application state: conversation and task
  state, registrations, relationships, preferences, summaries, and filesystem
  references.
- The filesystem owns datasets, trained analyzers, exports, logs, caches, temporary
  work, and other large or user-openable bytes.
- Services coordinate both stores and keep records and owned files consistent.
- User-selected source files remain user-owned provenance. Xenix does not mutate or
  delete them as a side effect of removing app state.
- Remote worker files are reproducible execution/cache state, never canonical
  product storage.

Schema versions, table shapes, serialized enum values, runtime directories, and
storage libraries are owned by source, migrations, configuration, and tests.

## Identity and Consistency

- Dataset registrations reference service-owned tabular materializations.
- Importing an attachment first preserves its source-file artifact identity; the
  Agent intake path may then register one or more datasets from that source.
- Data preparation registers derived data separately and retains available lineage
  to its source inputs.
- User-openable result identity and activation follow the
  [artifact link contract](artifact-links.md).
- Trained analyzers and ML results use durable records that point to canonical local
  artifacts; remote paths never become registered authorities.

## Deletion Invariants

- Dataset disposal is allowed only when no workflow owns or references the dataset.
- Disposal removes a service-owned materialization, never a user-selected source
  file or a source dataset referenced by derived data.
- Artifact deletion is not a current cross-unit operation. Adding it requires an
  owner-aware file-and-registration contract.

## Verification

Storage models and migrations own the mechanical schema. Boundary coverage lives in
`tests/test_repositories.py`, `tests/test_services.py`,
`tests/test_storage_bootstrap.py`, and `tests/test_migrations.py`.
