# Slice 03 / Phase K — Document Removal Design Evidence

**Date:** 2026-07-23
**Finding:** KB-D40
**Evidence mode:** read-only source/contract inspection; no product code or local
Knowledge data changed
**Follow-up:** Phase K is now implemented and locally accepted; see
[Phase J/K implementation evidence](03-phase-j-k-implementation.md).

## User Outcome

The Knowledge Workspace must let the user delete one selected logical document.
After success, the document must disappear from the Workspace and must not be
returned by keyword, semantic, or hybrid retrieval. Xenix may remove its own source
snapshot, canonical content, Units, indexes, and related task state, but must never
modify or delete the file originally selected by the user.

MVP does not add a toolbar delete button, undo, a recycle bin, tombstone/audit
history, bulk deletion, or an Agent deletion Tool.

## Current Evidence

| Surface | Current fact | Consequence |
| --- | --- | --- |
| Workspace | `KnowledgeDocumentSummary` contains title/format/state/timestamps but no `document_id`; the table has no removal action. | A widget cannot name a stable command target without first changing the Workspace presentation DTO. |
| Service ownership | Product TDD and `KnowledgeService` explicitly keep it retrieval-only. | Deletion cannot be added as a convenience mutation on the lookup owner. |
| SQLite | Document is referenced by Unit, Import, Canonical Generation, and Derivation rows. Foreign keys have no `ON DELETE CASCADE`; FTS is maintained explicitly. | One owner must perform a tested dependency-ordered transaction. Deleting only `knowledge_document` fails or leaves search state. |
| Import/task history | Attempts point to document/source Artifact and use `planned_document_id`; derivations can self-reference retries. Import logs live in app-owned task directories. | Removal must cover the complete document lineage and must reject related active work rather than racing it. |
| Artifact/source CAS | Knowledge import registers its app-owned source snapshot as an Artifact. ArtifactService has no unregister method. Startup CAS cleanup preserves every SQLite-referenced source/canonical path. | The registration must be released through an owner-aware service seam before proven-orphan CAS cleanup can reclaim bytes. The user source path is outside this authority. |
| Keyword | FTS rows are separate from `knowledge_unit`; normal query joins also check `knowledge_document.active`. | Explicit FTS + Unit removal in the SQLite cutover gives immediate, inspectable keyword absence. |
| Semantic | Lance generations are immutable whole-Library projections. Strict lookup binds metadata, corpus/profile fingerprints, counts, and current Unit identities. | A per-document in-place vector delete is the wrong model. Affected Library generation metadata must be invalidated; strict identity already prevents a racing old snapshot from becoming current. |
| Rebuild | `notify_corpus_changed()` coalesces a text-vector task only when Embedding is configured and searchable content remains. | After invalidation, the existing index owner can rebuild the remaining corpus without creating a deletion-specific index pipeline. |
| Durable scope | Product TDD currently labels document removal UX as later work; storage ownership forbids deleting user-selected source files and requires an owner-aware Artifact deletion contract. | Phase K must update both durable contracts when implemented rather than treating deletion as UI-only behavior. |

## Selected MVP Contract

Use a new `KnowledgeDocumentLifecycleService` command boundary. It accepts explicit
`library_id` plus stable `document_id`, checks that the active document belongs to
that Library, and rejects queued/running Import or Derivation work with
`knowledge_document_busy`.

The service performs one hard application-state removal:

```text
SQLite visibility cutover
  guarded active-document claim + no-active-work predicate
  -> FTS -> Units -> Derivations -> Canonical generations
  -> Import attempts -> unreferenced Knowledge source Artifact registrations
  -> Document -> affected Library vector-generation metadata

post-commit maintenance
  unreachable import logs
  + proven-orphan source/canonical CAS
  + orphan vector generation directories

remaining corpus
  -> existing coalesced vector rebuild notification
```

Hard removal is intentionally chosen over `active=false`: the product has no undo
or audit requirement, and retaining a same-SHA tombstone would either block a clean
re-import through the unique `(library_id, source_sha256)` identity or require a
second reactivation state machine. Explicit repository ordering is chosen over a
schema-wide cascade migration because FTS, Artifact release, external task logs,
CAS, and vectors still require service coordination even if SQL children cascade.

The existing `active` field is still useful as an **uncommitted transaction claim**:
the first guarded writer statement flips it only if the exact document is active
and has no active Import/Derivation. The same transaction then hard-deletes the row.
If the transaction rolls back, the claim rolls back; if it commits, no inactive
tombstone survives. This makes busy admission and removal one SQLite ordering point
instead of a racy read followed by a delete.

All vector-generation metadata for the affected Library is invalidated because the
current schema cannot prove which immutable historical generations do or do not
contain the deleted document. This is rebuildable derived state. If other
searchable Units remain and Embedding is configured, the existing index service
queues one coalesced rebuild; an empty Library needs no replacement generation.

## UI Contract

Phase J supplies a progressively loaded Workspace document DTO with internal
identity. Phase K adds `Delete` to the context menu of a concrete Knowledge-content
list item. Right-click targets the item under the pointer even when another row was
previously selected; right-clicking empty viewport space exposes no deletion action.
There is no toolbar delete button. Choosing `Delete` opens a window-modal
destructive confirmation. The copy must say:

- which document will be removed;
- Xenix's imported copy, search data, and related task entries will be removed;
- the original file remains untouched; and
- the action cannot be undone.

The command runs off the UI thread. Dismissing the context menu or cancelling the
confirmation performs no call. A stale/missing row refreshes without claiming
failure-induced data loss; busy and unexpected failures show bounded translated
copy.

## Acceptance Boundary

The main black-box case is Import → Canonical → Derivation → keyword/vector lookup →
delete → lookup absence → same-SHA re-import. Multi-document and multi-library
cases prove isolation; a racing vector rebuild proves snapshot recheck; SQLite
foreign-key/FTS checks prove the cutover; shared/unshared CAS fixtures prove
reference-aware cleanup; UI tests prove confirmation and lifecycle behavior; frozen
smoke proves the packaged composition uses the same command boundary.

## Authorization State

Sir authorized adding Phase K to the task packet on 2026-07-23. This evidence and
the candidate Impact Handshake are documentation-only. No product code, migration,
destructive local-data exercise, commit, or publication is authorized yet.
