# Artifact Provenance Removal — Impact Handshake

## Status

**Awaiting Sir's whole-task confirmation before product-code mutation.** The Artifact decisions in this file remain active, but this is no longer an independently deployable storage/domain correction. It is an internal dependency of the single end-to-end migration rehearsed in [17-whole-task-implementation-rehearsal.md](17-whole-task-implementation-rehearsal.md). It implements the accepted decision that Artifact contains only Artifact-domain facts: it has no Thread/Turn/Message/Tool Call relationship, and it introduces no replacement ledger, `ToolResultMessage.artifact_refs`, deferred binding, or tombstone.

## Address and Object

| Area | Exact object | Intended change |
| --- | --- | --- |
| Artifact schema | `src/xenix/services/storage/models.py:ArtifactRow` | Remove `thread_id`, `turn_id`, `message_id`, and `tool_call_id` columns, foreign keys, and indexes. |
| Artifact domain API | `src/xenix/services/artifact_service.py:RegisterArtifactInput`, `ArtifactService.register_artifact`, `list_thread_artifacts`, `_validate_links` | Remove Conversation repository import, constructor dependency, all validation, all Conversation-ID inputs, and Thread-scoped listing. Registration must not require a persisted Conversation object. |
| Artifact repository | `src/xenix/services/storage/repositories/artifacts.py` | Remove `list_by_thread`, `list_by_message`, and `list_by_tool_call`; retain only Artifact-domain queries. |
| Conversation storage read/lifecycle coupling | `src/xenix/services/storage/repositories/agent_conversations.py:delete_thread`; `src/xenix/services/agent/conversation_store.py:ThreadSnapshot` | Remove conversation-owned Artifact deletion and remove Artifact rows from the canonical conversation snapshot. A UI may explicitly query Artifact later; an LLM snapshot cannot be an Artifact read model. |
| Agent/worker calls | `src/xenix/services/agent/tools.py`, `src/xenix/services/dataset_export_service.py`, `src/xenix/services/preprocessing_worker.py` | Stop forwarding `turn_id` and `tool_call_id` to Artifact registration. Retain ordinary bounded result values such as an `artifact_id` or URI, but not a normalized Artifact lineage field. |
| Forward migration | `src/xenix/services/storage/migrations.py` and schema/bootstrap tests | Add an explicit forward SQLite table rebuild; `create_all` cannot remove deployed columns or foreign keys. Preserve Artifact facts, discard only obsolete provenance. |
| Verification | Artifact, Agent tool/worker, conversation snapshot, storage bootstrap, migration tests | Replace provenance/owner-validation expectations with independence, schema, and preservation proof. |

## State Diff

### From

`ArtifactService` imports `AgentConversationRepository` and validates a Thread, Turn, Message, and Tool Call during registration. `ArtifactRow` persists four conversation foreign keys. Agent tools and a preprocessing worker must pass durable Turn/Tool Call IDs before their Artifact writes can succeed. Conversation deletion deletes Artifacts by `thread_id`; canonical `ThreadSnapshot` includes a list of Artifact rows.

### To

Artifact registration records only Artifact-domain facts. It accepts no Thread, Turn, Message, or Tool Call provenance and makes no Conversation/Harness query. A local tool or worker may register an Artifact before a provisional LLM exchange finalizes. The later finalizer either commits its bounded Tool Result or discards the exchange; it never reconstructs it from Artifact state. Conversation snapshots and deletion have no Artifact ownership behavior.

The migration preserves each Artifact's identity, kind, title, path, media/preview/metadata, ready state, and creation time. It intentionally drops every legacy Conversation value: Thread, Turn, Message, and Tool Call.

## Accepted Scope: No Conversation Scope

`ArtifactRow` retains no `thread_id` or other Thread label. An Artifact is globally URI-addressable domain state, not a Thread-scoped presentation row. `ArtifactService` and its repository expose no Conversation-derived listing or validation operation.

If a future product needs an Artifact grouping or presentation relation, it must be proposed explicitly at that presentation/domain boundary. It must not reinstate a hidden Conversation foreign key, an opaque Thread label, or metadata substitute inside Artifact.

## Blast Radius

- Existing v14 databases need a v14-to-v15 Artifact-table rebuild that removes all four Conversation columns. With SQLite foreign keys enabled, this must be a real forward migration, not a model-only edit.
- The three local Artifact-producing tool paths and the preprocessing worker lose their persistence ordering dependency on Tool Calls; ordinary result payload IDs/URIs remain available to users and tools.
- Deleting a Thread no longer deletes, labels, or validates any Artifact rows/files. This is an intentional ownership correction, not an orphan-cleanup promise.
- `ThreadSnapshot.artifacts` has no production reader today; its removal changes a test-only read projection and prevents the future LLM Conversation Service from becoming an Artifact aggregation service.
- Current migration and foundation tests that expect Turn/Message/Tool Call validation must be replaced; unrelated old Harness use of Turn/Tool Call identities is outside this narrow slice.

## Invariants

1. No `ToolResultMessage.artifact_refs`, Artifact lineage table, provisional Tool Call, deferred Conversation binding, or observability-to-conversation reconstruction is added.
2. ArtifactService never imports, queries, validates, or stores Conversation/Harness records or IDs.
3. Artifact registration is valid independently of whether a tool exchange later commits, is cancelled, or is lost on process exit.
4. A bounded ordinary tool result may still contain its own artifact ID/URI/value for user-visible output; that is output data, not a second Artifact-to-Message schema relation.
5. Artifacts never enter provider context, frontier eligibility, or retry/recovery logic.
6. The migration preserves Artifact domain rows and files; only the explicitly rejected Conversation columns disappear.

## Verification

1. Fresh bootstrap: Artifact table has no Thread/Turn/Message/Tool Call columns or foreign keys, and no Conversation-derived index.
2. v14 upgrade: a populated Artifact row keeps all domain facts and loses only the four legacy Conversation values; `PRAGMA table_info`, `foreign_key_list`, and indexes match fresh bootstrap.
3. Artifact service: registration succeeds without any Conversation row or Conversation-ID input; no Thread-scoped Artifact query remains.
4. Local and worker Artifact-producing tools: registration succeeds before any final Tool Call/Result persistence and no old provenance is passed.
5. Conversation deletion: it neither deletes nor validates Artifact records; a deleted-thread Artifact remains resolvable by URI.
6. Snapshot/context: no Artifact rows appear in the canonical conversation snapshot or provider input.
7. Focused PDM suites: artifact foundation, affected agent tool/worker tests, storage bootstrap, and migration tests; then the relevant broader agent suite.

## Out of Scope

- LLM Conversation Message/Tool Call schema migration, removal of old Turn/Run identities, provider normalization, and ToolExecutionContext redesign remain governed by later approved slices.
- General Artifact retention/garbage collection, naming collision fixes, data lineage, cross-process recovery, tool idempotency, and any future Artifact presentation-grouping relation are not introduced here.

## Accepted Disposition

Remove every Thread/Turn/Message/Tool Call Artifact relationship, including `Artifact.thread_id`; remove Conversation snapshots and Thread-deletion ownership; remove all ArtifactService Conversation validation and Conversation-derived listing. Do not replace those fields with lineage or presentation metadata.
