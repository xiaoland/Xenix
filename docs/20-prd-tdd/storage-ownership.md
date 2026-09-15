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

- Xenix-owned business objects use persistent positive integer IDs allocated by one runtime-local SQLite sequence. Database rows, service inputs, Tool schemas and canonical JSON use those same integers; URI and display boundaries use decimal text. Published IDs are never reused within that runtime, and allocation may leave gaps. Provider identifiers, configuration keys and content hashes are not business-object IDs.
- Dataset registrations reference service-owned tabular materializations.
- A table with columns and zero rows is a valid Dataset, including a cleaning result that removed every row. Registration and export preserve its schema; operations that require samples enforce that requirement at execution.
- Importing an attachment materializes one or more service-owned datasets and
  records original-file provenance with the Dataset import. It does not create
  an Artifact-to-Conversation relationship or make the user-selected source
  file an Artifact authority. Harness may derive an ephemeral Chatbot source
  presentation from that provenance; an unavailable original file never makes
  the canonical Thread unreadable.
- Data preparation registers derived data separately. DatasetService owns one
  derivation record per generated Dataset plus its ordered input edges; the record
  keeps the operation, parameters, optional Agent-authored explanation, and stable
  originating ToolCall reference. `derived_from_dataset_id` remains a legacy
  best-effort primary-parent projection, not the lineage authority.
- User-openable result identity and activation follow the
  [artifact link contract](artifact-links.md).
- Trained analyzers and ML results use durable records that point to canonical local
  artifacts; remote paths never become registered authorities.

## Deletion Invariants

- Dataset disposal is allowed only when no workflow owns or references the dataset.
- Disposal removes a service-owned materialization, never a user-selected source
  file or a source dataset referenced by derived data.
- Artifact deletion is not a generic cross-unit operation. Knowledge document
  removal is the narrow implemented exception: its lifecycle service first removes
  all Knowledge references in one SQLite transaction, unregisters only a
  metadata-and-path-verified Knowledge source Artifact with no remaining reference,
  and delegates physical CAS reclamation to the Knowledge content owner after
  commit. Artifact registration removal alone never authorizes byte deletion.
- A Knowledge document with active import or derivation work is not removable.
  Successful removal is a hard application-state cutover rather than a tombstone:
  FTS and Units are removed explicitly, the affected Library's immutable vector
  generation metadata is invalidated, and any replacement generation is rebuilt
  from the remaining corpus. Cleanup failure may leave reclaimable app-owned bytes
  but cannot make the document searchable again.

## Verification

Storage models and migrations own the mechanical schema. Boundary coverage lives in
`tests/storage/test_storage_bootstrap.py`, `tests/storage/test_migrations.py`, and
`tests/storage/test_storage_artifacts.py`.
