# Slice 02 — Knowledge Operations, Workspace, and Index Control

**State:** Closed through Slice 03 by Sir on 2026-07-24
**Opened:** 2026-07-22
**Scope rule:** this is one slice with internal phases, not one slice per finding

## Objective

Make the global Knowledge Base understandable and controllable as a product surface:
heavy import work executes outside the UI process and has readable logs; the
Workspace lists logical documents; Knowledge settings own Embedding, OCR, and index
controls; vector compatibility changes are explicit; users can rebuild real indexes;
and the carried Agent final-answer residual is repaired and re-verified.

Multimodal retrieval (`KB2-F06`) is explicitly outside this slice. Its research is
retained as a [parked follow-up](02-multimodal-retrieval.md), not an acceptance gate.

Slice 01 remains closed. Its two failed live final-answer cells are carried here for
later repair without changing their verdict.

## Admitted Findings

| ID | Finding | Current evidence | Target outcome |
| --- | --- | --- | --- |
| KB2-F01 | The live semantic benchmark produced the exact Dataset twice but omitted the required grounded rule/actions in the final answer. | Recorded in [Slice 01 / Phase B](01-semantic-hybrid-retrieval.md). | Diagnose later in this slice and grade only the final deliverables. |
| KB2-F02 | Import execution is not process-isolated and has no inspectable per-attempt log. | `KnowledgeImportService` owns an in-process daemon thread; ML uses spawned workers and `logs.jsonl`. | One import attempt executes in one spawned process; Queue users can inspect bounded logs. |
| KB2-F03 | The Workspace body does not list Knowledge content. | `KnowledgeWorkspaceDialog` renders description/status/actions and then stretch. | Render service-backed logical documents, not attempts, chunks, assets, or internal IDs. |
| KB2-F04 | Embedding compatibility changes have no confirmation or visible rebuild lifecycle. | A profile mismatch correctly excludes old Lance generations, but a later lookup may build a new generation implicitly. | Explain impact before save; rebuild is an observable task rather than a surprise lookup side effect. |
| KB2-F05 | Embedding and OCR controls do not have a Knowledge-owned Settings surface. | Embedding is inside AI; local OCR setup is inside the Workspace; Settings has only AI and ML Workers tabs. | Add a Knowledge Base tab and one direct Workspace-to-tab navigation path. |
| KB2-F07 | Users cannot manually rebuild indexes or select which projection to rebuild. | Vector generations build lazily; FTS has no user command. | Add a selection sheet for keyword and configured vector indexes with visible task state. |

## Guardrails

- SQLite remains the authority for imports, logical documents, current canonical and
  retrieval generations, current Units, and index-generation metadata. A worker
  result is a proposal until the parent coordinator validates and publishes it.
- Source and canonical bytes remain content-addressed; LanceDB remains a rebuildable
  projection. An index task never becomes a second content authority.
- `KnowledgeImportService` still ends at canonical-ready. Post-canonical derivation
  and index publication remain separate lifecycle operations even when the UI groups
  them as user-visible activity.
- Raw source paths and document passwords are transient. Passwords, API keys,
  document text, provider payloads, and unbounded exceptions never enter task
  manifests, SQLite, Tool values, or logs.
- The Workspace consumes service DTOs and stable commands. It does not inspect ORM
  rows, derive storage paths, or compute index compatibility.
- Existing `knowledge.lookup` keeps one canonical result plane. A future visual
  reference may cross it only when another operation can consume that reference.
- The global Library remains the only visible library, while every service/query/task
  retains `library_id` so multiple instances remain an extension rather than a
  migration.
- No phase may start product-code changes until its exact Impact Handshake is shown
  to Sir and Sir explicitly authorizes the start. Commits require a separate command.

## Target Topology

```text
Knowledge Workspace / Settings
          |
          | commands + immutable DTOs
          v
parent Knowledge coordinators ----------------------> SQLite authority
          |                                               |
          | one-shot transient input                      | current Units /
          | (path/password never persisted)               | generations
          v                                               v
spawned import worker / background index task       FTS5 / Lance projections
          |
          | staged source/canonical/index proposal
          | + bounded log events + result manifest
          v
parent validates paths, hashes, profile/corpus snapshot
          |
          +--> append safe logs.jsonl (single writer)
          +--> atomic filesystem publication
          +--> one SQLite publication transaction
```

The import process boundary removes parsing/OCR/native-library work from the UI
process. Index work is serialized on a service-owned background thread for this
slice; neither path delegates application authority to its executor.

## Internal Phase Plan

| Phase | Purpose | Entry gate | Exit evidence |
| --- | --- | --- | --- |
| A — Import process and logs | Spawn one process per attempt and expose safe logs. | Sir approves exact runtime/storage/UI surface. | Crash/cancel/success tests, no-secret log tests, Queue log UI, frozen-app worker exercise. |
| B — Workspace and Settings | Add logical-document list and Knowledge-owned configuration/navigation. | Phase A DTO/task state is stable enough for presentation. | Service/UI tests plus bilingual visual evidence. |
| C — Index lifecycle | Make compatibility, automatic freshness, confirmation, and manual rebuild explicit. | Settings ownership and task presentation are stable. | Compatibility matrix, task state, generation publication, UI confirmation/sheet, provider-call bounds. |
| D — Acceptance | Repair KB2-F01 and cross-review the completed slice. | Required A–C implementation phases are accepted. | Focused/full/package tests, final-answer benchmark, and global Import/Storage/Tool/UI/runtime review with Sir. |

Phases are sequencing checkpoints only. Slice 02 closes as one cohort.

## Phase A — Import Process and Logs

### Recommended boundary

Reuse the ML execution **shape**, not ML task rows or ML domain services:

- `KnowledgeImportService` remains the application façade and lifecycle coordinator.
- A Knowledge-specific worker runner starts one Windows `spawn` process for one
  import attempt. MVP concurrency remains one attempt at a time to bound Docling/OCR
  memory; concurrency can become policy later.
- The child has no SQLite session and cannot publish Artifact, document, generation,
  or terminal import state. It writes only inside its assigned staging/task root.
- The parent snapshots and hashes the source into the app-owned source CAS before
  launch. The child receives only that snapshot path plus an optional password through
  one-shot in-memory IPC; neither is written to durable request/result manifests or
  logs.
- The child verifies the snapshot, runs probe/normalize/route/parse/canonical work,
  emits bounded structured events, and writes a bounded result manifest. The parent
  reopens the canonical bundle and verifies the full envelope identity before any
  SQLite publication.
- The parent validates containment, schema, hashes, attempt identity, and cancellation
  state before Artifact/CAS and SQLite publication. A malformed or crashed child
  cannot make partial content current.

```text
UI enqueue
  -> parent persists queued attempt
  -> parent snapshots source into source CAS
  -> dispatcher starts child with transient CAS path/password
  -> child parses/canonicalizes into attempt staging
  -> child writes bounded result manifest and exits
  -> parent validates result
     -> success: publish CAS/canonical + current pointers + terminal state
     -> failure/cancel/crash: publish safe attempt state; no partial document
```

Encrypted-document retry retains the existing rule: a password exists only for that
attempt. After an app/worker restart, an attempt that still needs a password asks the
user again.

### Log contract

Each attempt receives an app-owned task directory such as
`artifacts/knowledge/tasks/imports/<attempt-id>/` with `logs.jsonl`. The parent is the sole
durable log writer: it validates bounded child events received over IPC and appends
its own lifecycle events before and after the child. A bounded entry intentionally
contains only content-free tokens:

```text
schema_version, timestamp, level, phase, event_code
```

It never contains raw paths, passwords, API keys, document body/excerpts, provider
request/response bodies, tracebacks with user data, or arbitrary child stdout. A
broken event channel loses optional detail but still records a bounded child-exit
event; it never falls back to copying stderr verbatim. The Import Queue adds a
`View Log` action that opens a read-only, modeless log surface;
the UI reads through a service DTO and never discovers the path itself. Parent
coordinator events and child events share the same safe schema.

Cancellation is cooperative between stages, followed by bounded terminate/kill as a
fallback. The parent owns the final state and records child exit class without
persisting an unbounded exception.

## Phase B — Workspace and Settings Information Architecture

### Workspace body

The body lists **logical documents**. Import attempts stay in Import Queue; Units,
chunks, canonical generations, assets, hashes, and storage IDs remain internal.

Recommended service DTO:

```text
KnowledgeDocumentSummary
  title
  source_format
  content_state        # ready / processing / needs_attention / no_searchable_text
  imported_at
  updated_at
```

Recommended visible columns are Name, Type, Status, and Updated. A global status
strip reports keyword/vector index state because a Lance generation covers the whole
Library; pretending that vector readiness is an independent per-row fact would be
misleading.

The Workspace toolbar becomes:

```text
Import... | Import Queue... | Rebuild Indexes...              Settings...
```

An empty list owns the empty state. Selection/detail/open/remove behavior is outside
this admitted scope unless separately discussed; Slice 02 does not invent it merely
to fill a context menu.

### Knowledge Base Settings tab

Settings tab ownership becomes:

```text
AI              -> LLM providers and Agent model roles
Knowledge Base  -> Text Embedding, OCR, Indexes
ML Workers      -> ML execution workers
```

The current Embedding card moves from AI. Current local PaddleOCR readiness/setup
moves from the Workspace into the OCR card; remote OCR credentials are added only
when their adapter contract is admitted. The Indexes card shows derived status and
opens the same rebuild sheet as the Workspace.

The Workspace may project a concise read-only warning when OCR is unavailable and
image/scanned content will lack searchable text, with a link to Knowledge settings.
It does not retain a second install/configuration control.

The Workspace `Settings...` action asks the Main Window to show its one shared
Settings dialog at a stable `KNOWLEDGE_BASE` tab key. It must not create a second
Settings dialog, duplicate form state, or navigate by a fragile numeric tab index.

## Phase C — Index Compatibility and Rebuild Control

### Compatibility, not “any edit”

The existing profile fingerprint already identifies vector behavior. Rebuild impact
must follow that semantic boundary:

| Change | Rebuild text vectors? | Reason |
| --- | --- | --- |
| provider key, protocol/dialect, normalized base URL | Yes | Endpoint/model semantics may differ. |
| model | Yes | Embedding space changes. |
| requested dimensions | Yes | Vector shape/space changes. |
| adapter, encoding, or text-preparation version | Yes | Generated vector semantics may change. |
| API key | No | Credential changes access, not vector meaning. |
| batch size or timeout | No | Execution policy changes only. |
| disable Embedding | No deletion/rebuild | Semantic modes become unavailable; compatible generations remain derived data. |
| re-enable the exact profile | Only if corpus/profile generation is absent | A compatible current generation can be reused. |

Recommended confirmation trigger: the compatibility fingerprint changes **and** the
Library has current searchable content. This is more truthful than warning on API-key
or timeout edits. If Sir wants confirmation on every Embedding edit, the dialog copy
must not falsely claim that every edit rebuilds vectors.

The modal offers:

1. `Save and rebuild now` — recommended; save, enqueue an observable vector job.
2. `Save; rebuild later` — keyword remains available; semantic/hybrid stay unavailable.
3. `Cancel` — change neither settings nor index state.

Saving does not perform provider work inside the modal or UI thread. If enqueue fails,
the settings save remains visible and index status becomes `Needs rebuild` with a
retry action.

A vector job freezes one validated settings/profile and corpus snapshot. The API key
remains settings-owned and is read only by the provider operation; it is never copied
into index-task metadata or logs. Task metadata stores the non-secret profile
fingerprint. The coordinator rechecks both profile and corpus before publishing a
completed staging generation, so a mid-build settings/import change cannot make the
wrong vectors current.

### Normal freshness and lookup behavior

Recommended lifecycle:

- A completed derivation/corpus change coalesces an observable vector rebuild when
  Embedding is enabled. This is indexing triggered by an explicit import, not a
  hidden side effect of an Agent lookup.
- A compatibility-changing settings save follows the modal choice above.
- Manual rebuild is a force/repair control.
- `knowledge.lookup` never creates an index. Explicit semantic/hybrid modes report
  unavailable while no exact generation exists; `auto` reports and uses keyword.

This preserves the accepted rule that Import has no Embedding/Lance dependency: a
separate index coordinator observes current derivation state and schedules work.

### Rebuild sheet

The window-modal sheet lists only real projections:

- `Keyword index` — rebuild SQLite FTS5 from current SQLite Units; no provider call.
- `Text semantic vector index` — embed current Units using the frozen configured
  profile; show unit count and an estimated request count before submission.
- A future `Visual vector index` appears only when a multimodal profile and visual
  corpus are actually supported. A disabled promise is not shown in MVP UI.

Re-extracting text, rerunning OCR, or re-slicing Units changes source projections and
is not mislabeled as “rebuild index.” Those are separate repair/reprocess commands if
later admitted.

FTS replacement occurs in one SQLite transaction so WAL readers see a coherent old
or new projection. A manual vector rebuild over an unchanged compatible corpus keeps
the current healthy generation usable until atomic publication. After a corpus or
profile incompatibility, semantic retrieval remains unavailable while the new
generation builds; keyword retrieval remains available.

Index state is derived from current corpus/profile/generation plus any active job;
the UI does not persist a competing `is_ready` boolean. Minimum public states are
`Ready`, `Building`, `Needs rebuild`, `Unavailable`, and `Needs attention`.

## Phase D — Acceptance and Carried Benchmark

`KB2-F01` diagnosis distinguished:

- an Agent instruction/finalization failure;
- an answer-oracle vocabulary failure; and
- a retrieval/evidence availability failure.

The evidence showed an answer-oracle vocabulary failure: the terminal answer stated
the required three-week target, inventory-gap calculation, non-positive exclusion,
and exact recommendations, but used equivalent Chinese wording and a Unicode minus
sign that the old oracle rejected. The repaired oracle still reads only the final
Assistant and Dataset surfaces; it accepts bounded semantic equivalents rather than
Tool telemetry or arbitrary numeric coincidence.

The same isolated cell was rerun after that bounded repair. The Agent's terminal
Assistant/Dataset/Artifact/chart deliverables remain the semantic authority; Tool
Calls and ToolResults are diagnostic evidence only.

On 2026-07-22 the live `kimi/kimi-k2.6` cell with the configured independent
Embedding provider passed: run completed, semantic verdict passed, integrity was
true, persistence succeeded, and pytest reported `1 passed`. Offline oracle
regressions reject answers that contain the expected numbers without the business
rule.

Before Slice 02 closes, perform a global review across Import, canonical storage,
derivation, keyword/text-vector projections, Settings, Workspace task
state, Tool contracts, conversation replay, and packaged execution. Sir must be
reminded of this gate even if all internal phases pass independently.

## Approved Impact Handshake

Sir approved this boundary, including the recommended decisions, on 2026-07-22.

- **Address and object:** `KnowledgeImportService._process_import` plus new
  Knowledge-specific worker runner/entrypoint and log reader; Knowledge task layout,
  schema v21 index-task metadata, `KnowledgeRepository`, `KnowledgeSemanticService`,
  a new index coordinator, `KnowledgeDerivationService.derive_now`, app composition;
  `KnowledgeWorkspaceDialog`, `KnowledgeImportQueueDialog`, `SettingsDialog`,
  `MainWindow` navigation, translations, benchmark fixtures, tests, packaging, and
  durable owners.
- **State diff:** in-process opaque import and lookup-time implicit vector builds
  become process-isolated observable operations; an empty Workspace becomes a logical
  document list; AI-owned Embedding becomes Knowledge-owned configuration; index
  compatibility/rebuild becomes explicit. Multimodal state does not change.
- **Blast radius:** app startup/shutdown, Windows process spawning/frozen resources,
  task directories, SQLite migrations if task/index state needs new rows, settings
  save behavior, import/index latency/provider calls, bilingual
  UI, packaging, and benchmark fixtures.
- **Invariants:** parent/SQLite authority, immutable CAS/Lance publication, no secrets
  or raw paths in persistence/logs, global-library UX with `library_id` extension,
  single ToolResult plane, text lookup backward compatibility, and user-owned source
  files/settings remain intact.
- **Verification:** black-box process/crash/cancel/publication tests; log redaction;
  fresh/prior migrations if required; document-list DTO/UI tests; tab navigation and
  confirmation matrix; automatic/manual index generation tests; provider-failure and
  call-count bounds; packaged worker/Lance exercise; final-answer benchmarks; global
  cross-workstream review.

## Accepted Decisions

1. Show the Embedding confirmation only when a vector-space compatibility fingerprint
   changes and the Library has current searchable content.
2. A completed corpus change automatically enqueues a visible/coalesced vector job
   when Embedding is enabled. `knowledge.lookup` never creates an index.
3. Import Queue remains import-specific. Index state and errors appear in the
   Workspace and Knowledge Base Settings instead of introducing a broad Activity UI.
4. Multimodal work is parked outside Slice 02.

## Implementation Evidence

- Phase A: real spawned PID, success/crash/cancel/no-partial-publication, bounded
  content-free logs, modeless log viewer, and frozen worker exercise are covered by
  import worker/service/UI/package tests.
- Phase B: logical-document DTO/list, unavailable and empty states, one stable
  Knowledge Base Settings tab, exact Workspace navigation, and off-UI-thread OCR
  readiness/install tasks are covered by service/UI/i18n tests.
- Phase C: compatibility matrix, persisted/coalesced rebuild tasks, explicit FTS and
  text-vector commands, no lookup-time build, atomic generation publication, stale
  failure handling, and empty-corpus suppression are covered by index, semantic,
  migration, UI, and composition tests.
- Combined focused verification on 2026-07-22 passed `116` tests; subsequent UI,
  lifecycle, empty-corpus, and task-claim concurrency regressions passed. The live
  final-answer benchmark passed in
  `build/agent-harness-benchmarks/slice-02-final-answer-20260722`.
- The public `pdm run test` entry passed on the final acceptance baseline: `631`
  non-UI tests passed with `2` platform skips, then all `58` Qt main-window tests
  passed. `pdm run check` and both translation catalogs passed.
- `pdm run package` completed and `pdm run smoke-package` passed against the frozen
  executable, including the Knowledge import spawn and native Docling/PDFium,
  pikepdf, Zstandard, Lance, and Paddle resource seams.

## Cross-workstream Review Preflight

| Boundary | Reviewed convergence | Result |
| --- | --- | --- |
| Import → Storage | Child owns heavy staged computation only; parent validates canonical identity and alone publishes Artifact/CAS/SQLite state. Cancellation/crash leaves no current partial document. | Coherent |
| Storage → Indexes | SQLite owns documents, Units, generation metadata, and task state; CAS owns immutable bytes; FTS/Lance remain replaceable projections. Empty text does not enqueue a doomed vector job. | Coherent |
| Derivation → Index task | Successful Unit publication notifies after commit; enabled searchable corpora coalesce vector jobs. Claim/enqueue share a short lock so a running task cannot absorb work it did not snapshot. | Coherent |
| Indexes → Tool | Rebuild freezes/rechecks corpus and profile. `knowledge.lookup` only reads an exact current generation, never performs provider/index work, and keeps one minimal ToolResult plane. | Coherent |
| UI → Services | Workspace lists logical documents; Queue lists attempts/logs; Knowledge Settings owns Embedding/OCR/index state; shared stable navigation and background OCR/index work keep UI authority-free. | Coherent |
| Runtime/package | Startup recovery requeues interrupted derived tasks, shutdown preserves parent authority, hidden imports/resources are frozen, and packaged smoke exercises the spawned worker. | Coherent |

The requested global review across the Knowledge workstreams continued through
Slice 03. Sir accepted the coupled result and closed the complete follow-up task on
2026-07-24. Multimodal retrieval remains parked and was not smuggled into this
result.

## Closure

Slice 02 is closed through the accepted Slice 03 convergence and final review. Its
historical implementation and documentation commits remain unchanged.
