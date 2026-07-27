# Dataset Block Contract Reduction / Chatbot Source Projection Stage

## Status and Authority

Sir opened this stage on 2026-07-15 and confirmed the target `DatasetBlock`
summary fields and unavailable-source product rule. On 2026-07-15 Sir
authorized implementation of this stage **excluding `data.list` and its
scope-enforcement extension**. This packet records that bounded authority;
it does not authorize a database rewrite or unrelated product changes.

Implementation is complete and awaits Sir's manual acceptance. `data.list`
and scope-enforcement remain deliberately deferred.

## Triggering Evidence

Opening historical Thread `3a36671597724ac29415e2105ebcd3b2` failed because
its v14-to-v15-migrated Dataset block carried 50 `preview_columns`, while the
new typed block algebra imposed a 32-item maximum. The old, unbounded
attachment projection was copied raw into `content_blocks` during migration;
it is not data corruption. Nine local historical Dataset blocks have the same
shape.

The incident also exposed an architectural overload: the current canonical
UserMessage persists both a visible `SourceAttachmentBlock` and a hidden,
provider-visible `DatasetBlock`. The former carries Artifact/file metadata;
the latter carries schema/UI metadata. Both cross the provider boundary today.

## Facts That Constrain the Design

The materialized Dataset data and the original source file are different
resources:

- A current import materializes Dataset data to app-owned Parquet under
  `state/datasets/imported/<dataset_id>.parquet`.
- The original user-selected file is not copied or owned by `ArtifactService`.
  Its provenance is held by `DatasetImportRow` as original name, path, and
  format; that external path may later disappear.
- Existing `ArtifactRow` registration also records that original path, but has
  no durable Dataset-to-Artifact relationship. It is therefore duplicate,
  unowned source state, not a valid resolver key.
- `row_count` and `column_count` are available at import time but are not
  columns of the current Dataset storage row. A canonical block records them
  as historical facts; a reopen resolver must not try to reconstruct them by
  rereading a file.

Accordingly, a Chatbot "source attachment" retains its current product
meaning: the original user-selected source file, not a silent substitution of
the materialized Parquet Dataset. If that original file is unavailable, the
Dataset can still be used by tools when its app-owned data survives, but its
source-open action is unavailable.

## Accepted Dependency Topology

```text
UI source selection (transient name/path)
    -> Agent Harness coordinates import
    -> DatasetService materializes Dataset data and owns DatasetImport source
       provenance
    -> Harness submits one canonical DatasetBlock to LLMConversationService
    -> LLM adapters serialize only DatasetBlock's bounded LLM meaning

LLMConversationService Thread/Message snapshot
    -> Harness pure structural event projection
    -> Harness-only enrichment through a read-only Dataset source resolver
    -> Chatbot-only Source Attachment presentation
    -> Chatbot UI
```

Authority remains single and directional:

- `LLMConversationService` is the sole canonical Thread/Message writer. It
  knows no DatasetService, ArtifactService, Harness, file path, or Chatbot
  presentation.
- `DatasetService` owns Dataset data plus source provenance. It exposes a
  read-only `dataset_id -> source presentation` query; this is not a second
  conversation store or writer.
- Harness is the coordinator and presentation projector. It may depend on the
  two deep services, but neither service depends on Harness.
- Chatbot-only source data is ephemeral. It is never a canonical Message
  block, provider input, recovery input, or new persistence authority.

The pure structural projection may remain independently callable without a
resolver. Harness performs the optional enrichment after it receives the
snapshot. This preserves snapshot-driven Chatbot Events without making a live
file path part of LLM conversation state.

New imports must stop pre-registering an original-file Artifact solely to put
it into a conversation Message. Do not recover the relation by matching file
paths and do not register an Artifact during reopen projection. `DatasetImport`
is the sole durable source-provenance owner for this flow. ArtifactService
continues to own genuine artifacts elsewhere, independently of conversations.

## DatasetBlock Target Contract

Every newly written Dataset block contains exactly these bounded fields:

```text
dataset_id
name
row_count
column_count
```

They have distinct meanings:

- `dataset_id` is the opaque Dataset identity used by tools.
- `name`, `row_count`, and `column_count` are the compact historical snapshot
  attached to the importing UserMessage. They are not live Dataset authority
  and are not refreshed when a Dataset is renamed or changed.
- `name` is a logical Dataset display name, never a persisted source filename
  or path. When an import has no separate display name, it may be initialized
  from a sanitized source stem; the full filename, extension, and path remain
  DatasetImport provenance rather than Message content. New writes must
  normalize/reject path-shaped values before adapter serialization.

Remove from new canonical Dataset blocks:

```text
chatbot_visible / legacy visible
preview_columns
source_format
file_name
```

Each block class supplies a safe, bounded textual fallback for adapters, e.g.
the Dataset identity and its historical name/counts. No list of columns, local
path, source format, or source filename crosses to a provider.

A Dataset block is written only on the UserMessage that imports/attaches that
Dataset. It is never silently repeated on later UserMessages. Chatbot display
policy is based on block type: canonical Dataset blocks do not render as raw
Chatbot attachments; Harness projects their source-attachment presentation
instead, avoiding a duplicate UI attachment and avoiding any UI flag in the
canonical model.

## Chatbot Source-Attachment Contract

The resolver receives only a `dataset_id` from the canonical snapshot and
returns a bounded, read-only presentation record. It must include enough
information to deduplicate workbook-sheet imports originating from one source
and to choose a stable display label. A Chatbot-only source-attachment block
may carry the source file name and an in-process UI opening path.

The opening path is a UI-bound capability, not ordinary event content:

- it never enters `conversation_message`, a provider payload, or a tool result;
- it is absent/redacted from generic Chatbot-event logging or serialization;
- the renderer checks availability again at click time;
- it never changes Chatbot event identity, which derives from canonical message
  identity and block order.

Unavailable source resolution is a soft projection result, never a Thread
open failure:

| Resolver outcome | Chatbot behavior |
| --- | --- |
| Original source path is available | Show the ordinary source attachment with an open action. |
| Source metadata exists but path is moved/missing | Show the same bounded source label as unavailable; disable/fail the open action locally. |
| Dataset/import metadata is deleted, legacy, or malformed | Keep opening the Thread; use the DatasetBlock name as bounded fallback or omit only the source presentation. |

Do not silently open app-owned Parquet in place of the original source file;
that would change the meaning of the existing source attachment. A future
"open imported Dataset" affordance is a separate product decision.

## Deferred: Data Availability Tooling

`data.list` is intentionally out of this implementation. The later tool must
remain LLM-owned, use only `ToolExecutionContext.dataset_ids`, never fall back
to a global Dataset list, and arrive together with scope-membership enforcement
for relevant concrete data tools. It must not be smuggled into this source
projection slice.

## Compatibility and Historical Read Contract

1. Do not rewrite immutable final Message rows solely to remove deprecated
   fields.
2. Historical Dataset payloads may carry `visible`, `preview_columns`,
   `source_format`, and `file_name`. Decode them by discarding those obsolete
   fields before applying retained-field bounds. The 50-column historical
   Threads must reopen without database mutation.
3. Existing persisted `SourceAttachmentBlock` payloads remain decodable and
   projectable for historical Threads. New writes never produce them, and
   adapters must not forward their file/Artifact metadata to providers.
4. Unknown block types, malformed scalar types, invalid Dataset IDs, and
   invalid retained values remain fail-closed. A bad presentation lookup is
   isolated after snapshot loading and must not make the Thread unreadable.
5. Legacy summary fields absent from an old Dataset block use a bounded
   historical fallback; newly written blocks contain all four target fields.

## Required Verification

| Case | Required observation |
| --- | --- |
| New Dataset attachment | Canonical Message stores only `dataset_id`, `name`, `row_count`, and `column_count`. |
| Provider request | No source file name/path, source format, preview columns, visibility flag, or legacy source block metadata leaks. |
| Chatbot projection | Dataset blocks are suppressed as raw UI blocks; Harness emits one source attachment per original import, including multi-sheet deduplication. |
| Reopen, source available | A fresh Harness instance resolves and shows the source attachment without changing canonical rows. |
| Reopen, source unavailable | Thread opens; the UI shows a bounded unavailable source or safely omits it, with no exception. |
| Legacy content | 50-column Dataset blocks and persisted source-attachment blocks remain readable without DB mutation. |
| Boundary | LLM modules do not import Harness/domain services; UI-only path data never reaches canonical storage, providers, or ordinary logs. |

## Verification Record

Automated verification completed on 2026-07-15:

- `pdm run check` passed.
- The Stage 23-focused suite passed `99` tests across typed messages, title
  fallbacks, Dataset provenance resolution, Harness projection/streaming, and
  Qt main-window behavior.
- The complete suite passed: `270` non-UI tests and `57` Qt/UI tests. It
  emitted only the pre-existing third-party scikit-learn future/convergence
  warnings.
- Regression coverage proves that a historical 50-column Dataset payload
  reopens without rewriting its row; legacy source-attachment payloads remain
  readable; different imports with the same file name do not collapse; sheets
  from one import do collapse; missing/relative original source paths fail
  soft; and generic Chatbot-event serialization removes the UI opening path.

## Likely Implementation Surface

- `src/xenix/services/llm/messages.py` and adapter serialization tests
- `src/xenix/services/llm/conversation.py` title fallback and legacy-block
  compatibility tests
- `src/xenix/services/dataset_service.py` read-only source-presentation query
- `src/xenix/services/agent/harness_service.py`
- `src/xenix/services/agent/chatbot_events.py` and Chatbot UI event rendering
- focused message, provider-history, legacy-migration, Harness, UI-reopen, and
  streaming tests

## Next Step

Manual acceptance only. The implementation now:

- writes exactly the four Dataset summary fields and rejects new canonical
  source-attachment blocks;
- resolves original-source presentation through DatasetService after pure
  Harness projection, treating an absent/malformed source as a soft result;
- keeps historical wide Dataset/source-attachment rows readable without
  rewriting them; and
- keeps the UI opening target out of canonical/provider data and generic event
  serialization.

An intentionally accepted, bounded failure trade remains: source materialization
occurs before the immutable UserMessage append. If a later import in the same
submission or the append itself fails, a Dataset/import/file can remain a
domain orphan. This stage introduces no compensation transaction because that
would expand the accepted side-effect/recovery contract; it never creates a
canonical phantom Message.
