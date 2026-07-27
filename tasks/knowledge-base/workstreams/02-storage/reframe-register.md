# Retrieval-First Reframing Register

## Correction Recorded — 2026-07-15

Sir rejected the prior media-first storage draft for two reasons:

1. Recoverability and auditability are not MVP's primary target; retrievability is.
2. Storage must be designed from what knowledge is persisted and why it is read, not
   by starting with files, SQLite, artifacts, or index engines.

The prior Workstream 02 detail drafts were removed rather than retained as competing
guidance. Basic safety, source opening, and invalidation still matter, but only as
constraints that support correct retrieval.

## Accepted Working Order

```text
lookup contract
  -> Knowledge Unit and source-anchor model
  -> read/write/invalidation behavior
  -> required keyword/semantic projections
  -> persistence medium and technology choice
```

## Explicit MVP Non-Goals

- append-only audit history or full operation replay;
- backup/restore, quarantine, or general garbage-collection design as a primary
  workstream outcome;
- a generic knowledge graph, editable fact store, or automatic ingestion of every
  Xenix object;
- premature vector database/ANN selection; and
- a storage model defined by ArtifactService or a filesystem layout.

## First Blocking Decision

Clarify the policy for normalized Knowledge Unit text and lexical index data:

- **hard metadata-only SQLite:** select a dedicated retrieval sidecar; or
- **bounded retrieval corpus allowed in SQLite:** evaluate SQLite FTS5 plus an
  independent semantic projection.

This is a design clarification, not an implementation authorization.
