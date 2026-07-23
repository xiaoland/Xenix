# Slice 03 — Detailed Implementation Plan

**State:** Phases B–I locally accepted; final coupled review pending
**Decision date:** 2026-07-22
**Selected OCR backend:** official Paddle Inference C++ on Windows x64
**Slice boundary:** one Slice 03 with Phases B–I; these phases are not independent
slices and cannot silently drop another admitted finding

## Outcome

Slice 03 is complete only when all of the following are true:

1. Local OCR is an Xenix-built, unpack-and-run Windows component over official Paddle
   Inference C++; the user's machine does not install Python, pip, PaddlePaddle, or
   PaddleOCR.
2. Opening the Knowledge Workspace never waits for Docling imports, Unit-body scans,
   OCR process probes, or index integrity work.
3. The Workspace lists logical documents, has no introductory description, and
   presents quiet OCR/keyword/text-vector status in its footer.
4. One task query plane presents import, content preparation, and index work through
   the Workspace-local `Task queue` while retaining their separate execution and
   persistence authorities.
5. Retrieval projection compatibility is explicit. Legacy Units cannot become
   current merely because their rows still exist, and index status does not hash all
   Unit bodies.
6. Keyword, semantic, and hybrid retrieval still return the single accepted Tool
   value and pass the final-answer-oriented Knowledge benchmark.
7. TXT, DOC/DOCX, PPT/PPTX, PDF, JPEG, and PNG share the complete capability graph,
   and file-picker/drop inputs converge before task enqueue.

This slice does **not** add multimodal embeddings, PP-StructureV3, VLM, a generic
application-wide task table, or a second Agent Tool result plane. PPT/PPTX were
admitted later by Sir in Phase G; that decision supersedes the original non-goal but
does not rewrite historical Phase B–F evidence.

## Locked Design Decisions

### Official Paddle Inference C++

Xenix will own a thin native worker around the official PaddleOCR C++ inference
pipeline and official Paddle Inference runtime. The first supported model identity is
the current Chinese/English baseline:

- `PP-OCRv6_medium_det`; and
- `PP-OCRv6_medium_rec`.

No backend comparison remains on the critical path. The disposable compatibility
spike passed with PaddleOCR `v3.7.0` at commit
`b03f46425e8ff4442b268ce449e3eef758146cd4`, Paddle Inference `3.3.0`, OpenCV
`4.7.0`, and the exact official PP-OCRv6 medium model archives recorded in the
evidence. Paddle Inference `3.0.0` is not an acceptable fallback: it cannot load the
recognition model correctly.

The pass includes one required source adaptation. PaddleOCR `v3.7.0` incorrectly
assumes every detection model defines `DetResizeForTest.resize_long`; the selected
PP-OCRv6 model does not. Phase B owns a pinned, reviewed compatibility patch that
leaves the processor's default resize behavior intact. This is part of the runtime
lock and test evidence, not an untracked local fork. The engine choice may not
silently switch to ONNX Runtime or another backend if later worker/protocol evidence
fails.

### One install artifact, not a fictional single EXE

Official Paddle's Windows runtime needs the worker executable plus Paddle Inference,
OpenCV, Abseil/common, polygon-clipping, and related DLLs. Xenix therefore promises
one immutable **download archive** and one-click setup/repair, not one physical file.
The archive is extracted into one Xenix-owned generation directory and contains:

```text
xenix-knowledge-ocr-win-x64-<bundle-id>.zip
`-- xenix-knowledge-ocr/
    |-- xenix-ocr.exe
    |-- required native DLLs
    |-- models/
    |   |-- PP-OCRv6_medium_det/
    |   `-- PP-OCRv6_medium_rec/
    |-- runtime.json
    `-- THIRD_PARTY_NOTICES.txt
```

Runtime and model-pack identities remain separate fields in `runtime.json` even when
MVP ships them in the same archive. This preserves future independent model upgrades
without making the first installer flow multi-step.

### Distribution authority

The component is built in Xenix CI and published beside existing immutable Xenix
release artifacts in the configured OSS `published/` origin. The desktop client
never resolves Paddle dependencies from upstream at runtime.

- The build pins PaddleOCR source, Paddle Inference, OpenCV, model, and toolchain
  identities plus expected source/download hashes.
- The candidate produces the archive before packaging the app.
- Packaging embeds a small catalog containing artifact name, byte size, SHA-256,
  protocol version, runtime ID, and model-pack ID.
- The release manifest admits the OCR archive as a typed artifact instead of assuming
  that every artifact lives under `dist/velopack`.
- Candidate upload and publication verify the declared local, OSS, and public-URL
  digests before activation is possible.

The current Xenix Windows release is explicitly unsigned. SHA-256 therefore proves
artifact equality with the catalog embedded in that Xenix build; it is not described
as code-signing or publisher authentication.

### Runtime ownership and protocol

One spawned Knowledge import worker owns one native OCR child. The native child starts
only when the first routed page needs OCR, initializes the selected model pack once,
serves all OCR pages in that import attempt, and then exits. It owns no SQLite,
Artifact, canonical-document, index, network, or publication authority.

The protocol is versioned, length-delimited JSON over stdin/stdout:

```text
version     -> protocol_version, runtime_id, engine_version, build_id, architecture
self_test   -> success or bounded safe reason_code
initialize  -> exact model_pack_id + exact model directories
recognize   -> request_id + regions[{text, confidence, polygon}]
shutdown    -> acknowledgement
```

Input paths are resolved and bounded to the import attempt's staging area. Message,
image, output, stderr, and timeout sizes are bounded. Raw native diagnostics stay in
the import attempt's bounded local log and do not become Tool output or canonical
content. Cancellation closes stdin, waits a short grace interval, then terminates the
child process tree.

## Target Topology and Sequence

```text
MainWindow click
  -> construct lightweight KnowledgeWorkspaceDialog
  -> show shell immediately
  -> enqueue document/task/status snapshot
       -> bounded SQLite metadata only
       -> cached local-OCR manifest state only
  -> apply snapshot if generation is still current

Knowledge import worker
  -> probe / normalize / route / parse
  -> on first OCR page: start xenix-ocr.exe --stdio
  -> initialize exact runtime + model-pack generation once
  -> recognize every OCR-routed page
  -> close native child
  -> return candidate canonical result to parent
Parent import service
  -> retain existing validation and publication authority
  -> enqueue bounded retrieval derivation
  -> publish projection version/fingerprint/count atomically with current Units
  -> enqueue compatible keyword/vector index work as required
```

## Implemented Modification Map

| Area | Implemented addresses | Exact responsibility change |
| --- | --- | --- |
| Native worker | new `native/knowledge_ocr/` and `scripts/build_knowledge_ocr_runtime.py` | Build the pinned official Paddle worker, normalize its protocol, stage the DLL/model closure, run native tests, and emit one archive/catalog. |
| OCR deployment | `src/xenix/services/paddle_ocr_service.py`, `src/xenix/ui/ocr_deployment_tasks.py`, app composition in `src/xenix/app.py` | Replace Python/pip setup and boolean readiness with native generation activation, explicit states, cached fast status, async verification, and setup/repair. |
| Import OCR execution | `src/xenix/services/knowledge_import_worker.py`, `src/xenix/services/knowledge_pipeline.py`, OCR service tests | Hold one persistent native session per import worker, consume the engine-neutral region DTO, and preserve page-level routing/cancellation. |
| Retrieval compatibility | `src/xenix/services/storage/models.py`, `migrations.py`, Knowledge repository/derivation/semantic/index services | Add projection/corpus schema metadata, invalidate legacy current pointers during migration, idempotently re-derive, and make status metadata-only. |
| Lightweight UI seam | new lightweight Knowledge format/status/task-query modules, `src/xenix/ui/main_window.py`, `knowledge_workspace.py`, `settings_dialog.py` | Remove heavy import and synchronous refresh paths; show one async shell/snapshot; merge task presentation; move quiet status below the list. |
| Release delivery | `pyproject.toml`, `xenix.spec`, `release_config.py`, packaging/release scripts, candidate/publish workflows, packaged smoke | Make the OCR archive a typed immutable release artifact, embed its exact catalog, publish/verify it, and exercise the real frozen boundary. |
| UI contract | English/Chinese TS catalogs and Knowledge UI tests | Replace Import Queue copy, remove description/top status, add capability-driven task details/actions, and verify footer/accessibility behavior. |
| Durable knowledge | `docs/20-product-tdd/knowledge-base-boundary.md`, a new ADR for official Paddle C++ local OCR, `docs/40-deployment/runtime-state.md`, and `windows-distribution.md` | Record only the stable ownership, projection-compatibility, runtime-layout, and release contracts after code/tests make them true. |

## Phase B — Native OCR Component and Delivery

### B1. Pin and build the official runtime

Create an independently buildable native subtree:

```text
native/knowledge_ocr/
|-- CMakeLists.txt
|-- runtime.lock.json
|-- src/
|   |-- main.cpp
|   |-- protocol.cpp/.h
|   |-- paddle_ocr_engine.cpp/.h
|   `-- result_normalizer.cpp/.h
`-- tests/
```

Add `scripts/build_knowledge_ocr_runtime.py` to:

1. fetch only pinned upstream archives or use an injected verified local cache;
2. reject every source/model hash mismatch, including all build-time Abseil,
   Clipper, nlohmann-json, and `dirent.h` inputs currently fetched implicitly by the
   upstream CMake path;
3. configure and build the CPU-only Windows x64 worker with MSVC/CMake;
4. apply and verify the declared optional-`resize_long` compatibility patch;
5. stage the complete DLL/model closure from a manifest plus runtime load tests;
   this must include dynamically loaded `mklml.dll` and the pinned x64
   `vcomp140.dll` redistributable even though neither is reliably inferred from the
   worker's direct PE imports;
6. run `version`, `self_test`, a Chinese/English golden image, and a multi-image
   single-process test;
7. validate third-party notices and reject unexpected files; and
8. create a deterministic archive and emit its catalog payload.

The C++ code adapts only the needed official general-OCR detection/recognition
pipeline. It does not import table/layout/formula capabilities into the MVP promise.
The spike's sizing baseline is 349,530,496 runtime bytes plus 139,110,993 model bytes
(488,641,489 combined; 206,681,033 in a normal ZIP), with a 621,432,832-byte observed
peak working set and about 19.1 seconds for one cold end-to-end sample. These are
planning baselines, not release budgets. Phase B must record the deterministic
artifact's actual sizes and decide UI copy/timeouts from measured representative
Knowledge pages.

### B2. Replace runtime installation with generation activation

Refactor the current `paddle_ocr_service.py` boundary into three deep responsibilities
(filenames may be adjusted once code ownership is inspected during implementation):

- an engine-neutral OCR request/result/session contract;
- a Paddle bundle catalog/deployment service; and
- a Paddle native execution adapter.

The product status becomes one explicit state plus a safe reason code:

```text
checking | ready | not_installed | repair_required | installing | failed
```

`status_snapshot()` reads only the active manifest and cached verification record.
Full file hashing and `self_test` run asynchronously after install/repair, on explicit
repair, or when stale evidence requires it—not on Workspace paint.

Setup/repair follows one transaction-like path:

1. download the exact embedded-catalog artifact to `staging/`;
2. verify outer byte count and SHA-256;
3. validate archive paths before extraction;
4. verify every `runtime.json` member identity and digest;
5. run the native self-test from staging with exact model paths and network disabled;
6. atomically rename the complete generation and replace `active.json`;
7. retain the prior valid generation until the new pointer is durable; and
8. remove only Xenix-owned obsolete generations after successful activation.

The Python sidecar was never released. Sir authorized deleting its complete private
cache before this spike, so product code has no Python-runtime discovery, adoption,
migration, cleanup, or compatibility branch. `%USERPROFILE%/.paddlex` was not deleted
because it is outside Xenix's private runtime and another application may use it.

### B3. Integrate a persistent OCR session into import

Replace the current one-process/model-load-per-page path with a context-managed
session inside `knowledge_import_worker.py`/`knowledge_pipeline.py`:

- start lazily on the first OCR-routed page;
- pass every selected page through the same initialized child;
- normalize results to `regions[{text, confidence, polygon}]` at the service boundary;
- remove recursive dependence on PaddleOCR's Python nested response shape;
- propagate only stable reason codes to parent state/log DTOs; and
- preserve current page-level PDF routing and parent-side publication authority.

### B4. Make the component a first-class release artifact

Modify the release path coherently:

- `pyproject.toml`: add native build/catalog commands and place them before app
  packaging in `release-candidate`;
- `.github/workflows/native-candidate.yml`: install/use the pinned MSVC/CMake
  toolchain and cache only verified upstream inputs;
- `scripts/package_app.py`: embed the generated OCR catalog in release builds and
  fail a public build when the catalog is absent/inconsistent;
- `scripts/write_release_manifest.py`: advance the manifest schema and include typed
  artifacts from approved roots such as `dist/velopack` and
  `dist/knowledge-ocr`;
- `scripts/upload_oss_candidate.py` and `scripts/publish_oss_candidate.py`: resolve
  only manifest-approved relative paths, upload the OCR artifact immutably, and
  verify its public URL before publishing mutable feeds;
- `release_config.py`: derive the OCR artifact URL from the existing release origin;
  do not add a second user-configurable download authority; and
- packaged smoke: activate the locally built archive into an isolated app home and
  execute the actual frozen-app-to-native-worker protocol without Python/pip/network.

The app installer stays small; the optional OCR archive downloads only when the user
chooses local PaddleOCR setup or repair.

### Phase B exit gate

- The pinned PP-OCRv6 models load and match the accepted golden text/region contract.
- Ten images are recognized by one child PID with one model initialization.
- Fresh setup, interrupted download, corrupt archive, zip traversal, mismatched
  runtime/model identity, crash, cancellation, repair, and offline restart pass.
- The packaged executable activates and invokes the real native archive.
- No Python, pip, global PATH mutation, upstream model download, or `.paddlex` cache
  is used.

## Phase C — Retrieval Compatibility and Fast Workspace State

### C1. Add explicit retrieval-projection metadata

Advance SQLite through one forward migration (`v21 -> v22` in the current plan):

- `knowledge_document.retrieval_projection_version` — nullable integer;
- `knowledge_document.retrieval_content_fingerprint` — nullable text; and
- `knowledge_document.retrieval_unit_count` — non-null integer, default zero.

Add `knowledge_vector_generation.corpus_fingerprint_schema`, preserving historical
rows as schema 1 and writing new generations with the new schema. A successful
derivation publishes its current generation pointer, status, projection version,
content fingerprint, and unit count in the same SQLite transaction as Units/FTS.

The current corpus fingerprint is then computed from bounded active-document
metadata—document identity, current retrieval generation, projection version,
content fingerprint, and Unit count—instead of loading every Unit body. Vector rebuild
still reads Units because building vectors genuinely needs their text; status does
not.

### C2. Reconcile legacy projections without trusting them

The migration preserves source/canonical bytes and historical derived rows but does
not mark pre-version Units compatible. In the migration transaction, every previously
ready document without the current projection version is set to `pending`, its
`retrieval_generation_id` is cleared, and its new fingerprint/count fields are reset.
This makes old Units unreachable immediately after bootstrap, before any service or
UI can query them. A service-owned, idempotent startup reconciliation then:

1. finds active documents whose projection version is absent/stale;
2. queues exactly one canonical re-derivation per current canonical generation;
3. publishes a fresh bounded projection; and
4. queues the necessary vector rebuild after corpus metadata changes.

Old Units and old Lance generations are rebuildable derived data and may be reclaimed
only through the existing bounded cleanup policy. No second local data reset is part
of this implementation plan.

### C3. Introduce bounded status and snapshot services

Create a service-owned Workspace snapshot DTO containing only:

- logical document rows needed by the table;
- active/recent task summary counts;
- cached OCR state;
- keyword readiness/count; and
- text-vector readiness/profile compatibility.

Extract the supported-format registry and file-dialog filter from the heavy Docling
pipeline into a lightweight module. `main_window.py` may import the Workspace module
lazily, but the Workspace module itself must not import Docling/pipeline code merely
to render controls.

The first open performs no service refresh in `retranslate_ui()`, constructor, and
`showEvent` simultaneously. It shows once, starts one background snapshot, and applies
only the latest generation. Polling runs only while active work exists; an idle
Workspace does not perform a one-second loop.

### Phase C exit gate

- A v21 fixture with a legacy Base64 Unit upgrades safely, cannot be searched while
  stale, queues one re-derivation, and becomes searchable only after v22 publication.
- Fresh v22 bootstrap and v21 upgrade both pass schema/FK checks.
- Semantic status issues no `SELECT` of Unit text and remains bounded on a synthetic
  large corpus.
- On representative Windows hardware, the Workspace shell is visible within 500 ms
  and no single click-path event-loop segment exceeds 50 ms.
- Closing/reopening during a pending snapshot cannot apply stale UI state.

## Phase D — Unified Knowledge Tasks and Workspace Hierarchy

### D1. Add a task-feed query plane, not a task authority

Create `KnowledgeTaskQueryService` (name subject to local naming consistency) with one
presentation DTO:

```text
kind, target, status, phase, trigger, updated_at,
can_cancel, can_retry, can_view_log, can_view_details
```

The opaque internal reference needed for an action is not displayed as user content.
The query service performs bounded batch queries over existing import, derivation,
and index tables; it creates no generic task super-table and moves no lifecycle
transition into the UI.

Presentation folding rules are explicit:

- a normal import and its linked initial derivation appear as one user-intent row;
- an independent re-derivation/compatibility repair appears as `Content preparation`;
- a keyword/vector rebuild appears as `Index build`; and
- action availability comes from the owning service, so an index detail is not
  misrepresented as an import log.

### D2. Replace Import Queue with Workspace Task Queue

Rename the modeless dialog and open it from the Workspace toolbar. Recommended table
columns are `Type`, `Target`, `Status`, and `Updated`; phase/trigger and bounded error
detail appear in the details pane/tooltip to avoid a dense operations dashboard.

Import logs remain available for import-owned attempts. Index tasks expose persisted
phase/error details and their supported retry/cancel behavior. The dialog refreshes
asynchronously and only while visible or while active tasks exist.

### D3. Recompose the Workspace

The final body order is:

```text
toolbar: Import | Task queue | Rebuild indexes | Settings
document list / empty state
subtle separator
muted footer: Local OCR | Keyword | Text vectors
```

Remove the introductory description and the current top status blocks. The footer
uses a smaller font and palette-derived muted color, preserves accessible names and
contrast, and exposes setup/repair/rebuild actions through the existing explicit
buttons rather than tiny inline links.

Knowledge Settings consumes the same OCR status DTO as the footer. Its action copy
becomes `Set up`, `Repair`, or the in-progress phase according to the explicit state;
it no longer maps every incompatible worker/model condition to “not installed.”

### Phase D exit gate

- Running, successful, failed, cancelled, and retryable import/content/index examples
  render truthfully with only supported actions.
- Import log and index detail open the correct owning view.
- Workspace description/top status are absent; footer is below the list.
- English and Chinese translations, keyboard focus, empty state, resizing, dark/light
  palette, and modeless-dialog behavior receive functional and visual QA.

## Phase E — Acceptance and Cross-workstream Review

Run focused tests after each phase, then the repository delivery surface:

```text
pdm run test <focused Knowledge/storage/UI/release tests>
pdm run test
pdm run check
pdm run package
pdm run smoke-package
```

The Phase E acceptance corpus included born-digital/scanned/mixed PDF, TXT,
DOC/DOCX, JPEG, and PNG. It proved page-level OCR routing, bounded Units, FTS, vector
rebuild, semantic/hybrid lookup, and the Agent's final analysis/business answer.
At that checkpoint PPTX was diagnostic-only; Sir later superseded this boundary in
Phase G without rewriting the historical evidence.

Before Slice 03 closes, review Import, Storage, Tool, UI, OCR runtime, release, and
index-generation boundaries together with Sir. In particular confirm:

- import parent versus child/native publication authority;
- canonical generation versus retrieval projection/version authority;
- keyword/vector compatibility and rebuild ordering;
- Task Queue presentation versus the three task owners;
- Workspace status freshness versus bounded fast-path guarantees; and
- the single Agent ToolResult/final-answer benchmark contract.

## Phase F — Structural Convergence Repair

Sir accepted KB-D26–D31 on 2026-07-23 and explicitly asked for structural models
rather than accumulating format branches, retry flags, or status-specific patches.
This remains one Slice 03 closeout phase with three coherent batches.

### F1. Format capability graph and PDF evidence

- One immutable format registration names its probe, normalizer, route planner, and
  parser providers. `FileProbe`, `FormatNormalizer`, `ParserRouter`, and
  `ParseExecutor` become dispatchers over validated provider maps; adding a format
  does not add a branch to those dispatchers.
- A PDF page probe publishes bounded evidence and one explicit text state:
  `credible`, `suspect`, or `absent`. Evidence includes useful-character counts,
  suspicious Unicode, image coverage, and font facts. Routing consumes that state:
  credible uses native Docling, absent uses OCR, and suspect uses native+OCR hybrid
  when OCR is ready. Complex-layout is not claimed as a solved generic class without
  labelled evidence.
- The chosen page state, reasons, and bounded evidence enter the parse-plan/canonical
  pipeline descriptor. They are facts/projections, not a second content authority.

### F2. Projection snapshot, OCR generation, and process ownership

- Retrieval projection version advances once. Unit identity becomes deterministic
  from document, canonical generation, projection version, and ordinal. A repository
  corpus snapshot returns projection metadata plus ordered Unit DTOs from one SQLite
  read transaction and validates their implied identities/counts.
- Vector build embeds one frozen snapshot and publishes only if a second identity
  snapshot is equal. Fast status derives expected Unit identities from bounded
  document metadata and validates the Lance manifest; task success cannot disagree
  with strict lookup.
- Local OCR has one immutable runtime-generation descriptor and one freshness-bound
  verification record. Workspace paint remains manifest-only and fast; a background
  verification refresh hashes members/self-tests when evidence is absent or stale.
  Canonical provenance records the actual runtime/model/engine/protocol descriptor.
- The spawned Import worker is assigned to a Windows Job Object with kill-on-close.
  Cooperative cancellation remains first; forced cancellation terminates the owned
  job, so Docling/LibreOffice/native OCR descendants cannot outlive the attempt.

### F3. Route-complete acceptance

- Add labelled generated fixtures for born-digital, scanned, mixed, and suspect
  OCR-layer PDFs plus classifier coverage for broken-font evidence.
- Exercise a real native OCR generation through packaged
  Import→Canonical→Derivation→lookup, not activation/self-test alone.
- Rerun focused migration, pipeline, semantic/index, OCR/process, Workspace, package,
  and benchmark checks, then the full repository delivery surface.

### Phase F Impact Handshake

**Address and object:** `knowledge_formats.py`, `knowledge_pipeline.py`, new focused
PDF/process-boundary modules, projection/repository/derivation/semantic/index code,
the v22→v23 migration, Paddle OCR deployment/execution and Workspace snapshot seams,
packaged Knowledge smoke, focused tests/fixtures, and the Knowledge/deployment durable
contracts.

**State diff:** central per-format branching → validated capability/provider graph;
binary PDF text threshold → evidence-backed tri-state routing; separately read Units
and corpus identity → one immutable projection snapshot; shape-only OCR ready state →
freshness-bound verified runtime generation; root-process kill → owned process-tree
termination.

**Blast radius:** the then-existing six-format import routing and canonical pipeline
descriptors, one forward SQLite migration and re-derivation of derived Units, vector
generation compatibility/status, local OCR footer/settings state, cancellation, and
packaged Knowledge acceptance. Source/canonical user bytes and Agent Tool schemas do
not change.

**Invariants:** Import still stops at canonical-ready; only Derivation publishes
Units; no child owns SQLite/publication; Workspace never hashes runtime files or reads
Unit bodies on the UI thread; explicit semantic/hybrid requests never fall back
silently; one ToolResult and final-answer grading remain unchanged; no migration
deletes source/canonical content; multimodal/VLM stay out of scope. PPTX was outside
this Phase F handshake and was admitted separately in Phase G.

**Verification:** provider registration rejects missing/duplicate capabilities;
every PDF state has route/descriptor fixtures; the v22→v23 upgrade makes prior projections
stale and re-derives deterministic Unit IDs; the reproduced same-count vector race
cannot publish or report ready; stale/corrupt OCR verification converges without
blocking Workspace paint; a stubborn native descendant exits on forced cancellation;
and the packaged real-OCR import reaches bounded lookup evidence.

## Authorized Impact Handshake

Sir explicitly authorized this product-code boundary on 2026-07-22. The implementation
retains the following mutation and authority limits.

### Address

- new `native/knowledge_ocr/` buildable component and its build/test scripts;
- OCR deployment/execution services and import-worker/pipeline integration;
- SQLite models, repositories, v21-to-v23 migrations, derivation reconciliation,
  semantic status fingerprinting, and index generation metadata;
- MainWindow/Knowledge Workspace/Knowledge Settings/task-dialog UI plus translations;
- release configuration, packaging, manifest, OSS candidate/publish workflows, and
  frozen Knowledge smoke;
- focused storage/OCR/import/index/UI/release tests and durable deployment/unit docs.

### State delta and blast radius

- SQLite schema advances through v22 and v23; both migrations are forward-only.
- Existing source/canonical content is preserved; legacy retrieval projections become
  stale derived data and are rebuilt.
- Local OCR begins with an Xenix-owned native generation plus explicit model identity;
  the unreleased Python sidecar has no product migration path.
- The release manifest schema and candidate artifact set expand.
- Import Queue presentation becomes the Workspace `Task queue`; underlying task
  tables and service authorities remain separate.
- Workspace first-open timing and status refresh behavior change.

### Invariants

- No OCR child publishes or mutates application state.
- No migration deletes source/canonical user content.
- No legacy Unit is searched without current projection compatibility.
- No Workspace UI-thread path loads Docling, reads Unit bodies, invokes providers, or
  starts OCR.
- No runtime download is activated before exact catalog/manifest/hash/self-test
  success.
- No cleanup touches global `.paddlex` or unrelated user state.
- Lookup's accepted input/output and Agent final-answer grading stay unchanged.

### Reversibility

Code can revert before release; the SQLite migration cannot be rolled back in place.
Native runtime generations and indexes are disposable derived/cache state. Old SQLite
projection rows remain until bounded cleanup and do not regain current authority on
rollback. A rollback after migration therefore requires an explicitly compatible old
binary or a forward repair release, not database downgrade.

### Remaining gate

Implementation and local repository/package/native/live-benchmark evidence are
complete. The carried global review opened KB-D26–D31; Sir admitted the Phase F
Impact Handshake and all six repairs now have executable evidence. The attempted
final review then opened Phase G. The completed Phase H scope was later committed as
`b76a36e`; publication and final Slice 03 closure remain separately gated.

## Phase G — Presentation Import Completion

### Structural design

1. Add `pptx` and `ppt` to the immutable `KnowledgeFormatRegistry` as complete
   capabilities. PPTX binds an OOXML-presentation probe, identity/decrypt normalizer,
   PowerPoint route, and Docling parser. PPT binds a CFB-presentation probe and a
   LibreOffice-to-PPTX normalizer, then reuses the same route/parser contract while
   retaining `source_format=ppt` in canonical provenance.
2. Extract the existing DOCX package limits into a format-parameterized OOXML package
   verifier. DOCX requires `word/document.xml`; PPTX requires
   `ppt/presentation.xml`. The same path, entry-count, expansion, encryption, and
   compression safeguards apply without duplicating branches.
3. Generalize the legacy Office conversion adapter around an immutable conversion
   profile (`source suffix`, `target suffix`, LibreOffice filter, validation
   provider). DOC→DOCX and PPT→PPTX become two configurations of one bounded,
   cancellable subprocess boundary.
4. Configure the Docling adapter used inside the isolated Import worker and the
   simple-Office parser provider for `pptx`. No presentation-specific content tree
   is introduced: output remains one validated `DoclingDocument`, and normal
   derivation continues to skip embedded picture bytes while indexing bounded slide
   text/table content.
5. Introduce one Workspace-local file-drop adapter that extracts local URLs and emits
   paths only. Install it on the shell and document-list viewport; picker and drop
   both call one `_submit_import_paths` operation for stable ordering,
   deduplication, enqueue, queue opening, refresh, and bounded failure feedback.
   `KnowledgeImportService` remains the final file/admission authority.

### Accepted Impact Handshake

**Address and object:** `knowledge_formats.py`, provider implementations and Office
helpers in `knowledge_pipeline.py`, `knowledge_docling.py`, Knowledge import
error/copy surfaces, `knowledge_workspace.py`, translations, supported-format and
import/UI tests, PPT/PPTX fixtures, packaged Knowledge smoke, and active Knowledge
task/durable documents.

**State diff:** six implemented formats → eight; DOC-only legacy Office conversion →
profile-driven DOC/PPT conversion; picker-only Workspace → one picker/drop submission
operation. No SQLite schema, Tool schema, embedding protocol, or OCR runtime format
changes.

**Blast radius:** source admission, normalization/parser descriptors, worker allowlist,
package dependency closure, Workspace event handling, translations, and acceptance
corpus. Existing canonical generations and retrieval projections remain compatible.

**Invariants:** suffix alone is never authoritative; original files are untouched;
PPT normalization is explicit and checksummed; only DoclingDocument is canonical
content IR; no widget probes/parses/enqueues independently; mixed drops preserve
supported-file order and report unsupported entries safely; Import still ends at
canonical-ready and Derivation alone publishes Units.

**Verification:** registry/provider completeness; valid/spoofed/encrypted/unsafe PPTX
package fixtures; conditional real PPT→PPTX conversion; the existing 53 MB Chinese
PPTX through public Import→Canonical→Derivation→keyword lookup; picker/drop parity,
duplicates and mixed URLs; spawned Import-worker/package smoke; focused and full
repository tests. A real legacy PPT fixture is required before PPT is called a
release-ready promise.

### Phase G acceptance

- Format registry v2 exposes the nine suffixes across eight format capabilities and
  validates a complete probe/normalizer/route/parser provider graph.
- Generated PPTX, OOXML spoof/safety, encrypted PPTX, real PPT→PPTX, cancellation,
  picker/drop parity, import lifecycle, and public retrieval tests pass.
- The named 53,093,313-byte Chinese PPTX passes the public
  Import→Canonical→Derivation→lookup chain and returns the expected `菜单瘦身`
  evidence.
- The affected suite passes `88 passed, 1 skipped`; the complete repository suite
  passes `669 passed, 3 skipped` with only three existing scikit-learn warnings.
- A fresh 100,430,292-byte executable built successfully. The Phase G packaged smoke
  passed in 140.6 seconds under the then-current direct Docling-helper proof; Phase H
  supersedes that evidence with spawned Import-worker DOCX/PPTX proof.

Sir explicitly started Phase G on 2026-07-23. Implementation evidence is complete
and its resulting scope is included in `b76a36e`; publication and final Slice 03
closure remain separately gated.

## Phase H — Production Import Topology and Local Queue Naming

### Diagnosed cause

The failed import `67a1905431784f2c9d4a237318b9d6f6` reaches
`parsing_started`, then fails in the nested Docling execution boundary. The source
and CAS snapshot are byte-identical and valid, while direct Docling conversion of
that same snapshot succeeds. Existing persistence cannot identify the leaf exception
because the Docling child discards stdout/stderr and collapses non-zero exit, missing
output, and invalid output into one safe error code.

Phase G acceptance did not cover production topology: its named-fixture import used
the inline runner, and packaged smoke exercised the Docling worker directly. The
production-only path is:

```text
spawned Import worker -> nested Docling process -> 86.7 MB JSON -> Import worker
```

### Candidate Impact Handshake

**Address and object:** Docling execution in `knowledge_pipeline.py` and
`knowledge_docling.py`; supervision/result/event contracts in
`knowledge_import_worker.py`; PPT/PPTX import error-copy surfaces in
`knowledge_import_service.py`; production-topology import and packaged-smoke tests;
Workspace queue labels in `knowledge_workspace.py`, translations, and i18n/UI tests;
Phase H task and durable boundary evidence.

**State diff:** nested Docling process inside an already isolated Import worker ->
one supervised Import process executing Docling directly; opaque parse failure ->
bounded content-free stage/outcome evidence; inline/direct-helper presentation
fixture proof -> real spawned-import proof; `Knowledge tasks` /
`Knowledge Task Queue` -> Workspace-local `Task queue`.

**Blast radius:** Import worker cancellation/timeout behavior, Docling dependency
loading, frozen worker entrypoints and smoke, task-log event codes, user-facing error
summaries, translations, and the named large-PPTX acceptance path. No SQLite
migration, canonical IR, format capability, derivation/index/Tool contract, OCR
runtime, or multimodal behavior changes.

**Invariants:** the app process never imports Docling for an import; only the parent
service publishes SQLite state; forced cancellation kills the worker and all native
descendants; operation duration remains bounded; task diagnostics contain no
document body; one error authority feeds DB summary and task-log projection; queue
presentation still folds separate import/derivation/index authorities without a
generic task table.

**Verification:** a black-box production runner test imports the named 53 MB PPTX
through spawned worker -> canonical-ready -> derivation -> lookup; forced
cancellation and timeout leave no worker/descendant; staged failure fixtures produce
distinct safe task events; package smoke uses the spawned PPTX import path; PPT/PPTX
unsupported/normalization/package errors have accurate summaries; English/Chinese
button and modeless-dialog titles read `Task queue` / `任务队列` and survive
`LanguageChange`; focused tests, full suite, package, and package smoke pass.

### Current gate

Sir explicitly started Phase H. The nested Docling entrypoint and large intermediate
JSON handoff are removed; the spawned Import worker directly produces the canonical
IR and remains the only heavy-work isolation boundary. Worker result schema v2
records safe `failure_stage` and `diagnostic_code`, while the parent runner
distinguishes launch failure, timeout, process crash, and invalid result. The named
53,093,313-byte PPTX passes the default spawned Import→Derivation→lookup regression,
and bilingual Workspace queue naming passes focused UI/i18n verification.

The affected integration cohort passes `92 passed, 1 skipped`. The complete
repository gate passes `616 passed, 3 skipped` plus `58 passed` in the app-entry
session. A fresh 100,429,503-byte executable builds in 1,093.4 seconds; frozen
packaged smoke passes in 133.5 seconds and requires spawned DOCX/PPTX import plus
PPTX Derivation→lookup. Static checks and `git diff --check` pass.

Phase H is locally accepted and committed in `b76a36e`. The final coupled
Import/Storage/Tool/UI/OCR/runtime/release/index review with Sir and publication
remain separately gated.

## Phase I — Runtime Distribution and Vector Failure Truth

### Diagnosed causes

The active application is a source `scripts/run_dev.py` process. Its package root has
no generated `resources/knowledge_ocr/runtime_catalog.json`,
`XENIX_KNOWLEDGE_OCR_CATALOG` is unset, and no release origin is configured.
`PaddleOcrDeploymentService.install()` therefore fails at
`knowledge_ocr_catalog_unavailable` before creating a download or staging directory.
Supplying only the catalog would reveal the next missing input,
`knowledge_ocr_download_unavailable`. The 205,199,992-byte native archive and
generated catalog in `dist/knowledge-ocr` have matching size and SHA-256, so the
failure is above the native runtime.

The current corpus-change vector task starts from one ready projection with 67
bounded Units and fails before any LanceDB generation or SQLite generation row is
published. Its Embedding profile requests 64 inputs per HTTP batch. The selected
`qwen3.7-text-embedding` service accepts 20; bounded direct probes succeed at 20 and
return HTTP 400 at 21. `KnowledgeSemanticService` converts the leaf
`EmbeddingValidationError` into a generic semantic-unavailable error, and
`KnowledgeIndexService` persists only that generic code and summary.

### Candidate Impact Handshake

**Address and object:** OCR bundle-source/release composition in
`paddle_ocr_service.py`, `release_config.py`, `run_dev.py`, packaging and packaged
smoke; typed setup-task results and Knowledge Settings copy/logging; Embedding
request batching guidance, semantic/index error projection, task presentation, and
focused deployment/provider/index tests.

**State diff:** application-mode-dependent implicit catalog/release lookup → one
explicit bundle-source contract that supplies catalog identity plus local or remote
artifact access; swallowed OCR exception → typed content-free setup outcome;
provider rejection collapsed into semantic unavailability → one safe leaf error
projected through the existing index-task code/summary fields. The Embedding portion
is now implemented: Batch size remains an explicit user setting with a default of
20, and the current profile was corrected from 64 to 20 without changing vector-space
compatibility.

**Blast radius:** source/debug OCR setup, frozen/public release artifact resolution,
Knowledge Settings failure feedback, index-task retry copy, and Embedding request
batching. No SQLite migration, canonical IR, Unit identity, LanceDB schema, Tool
schema, model fingerprint, multimodal behavior, or native worker protocol change is
currently proposed.

**Invariants:** catalog/manifest/hash/self-test still gate activation; source mode
does not silently trust arbitrary archives; release and local transports share one
deployment state machine; no API key, document text, provider response body, or
vector is logged/persisted; provider-specific limits are not hard-coded into the
generic OpenAI-compatible protocol; batching-policy changes do not falsely
invalidate compatible vectors; retries never delete the prior failed task.

**Verification:** source composition installs the exact generated local archive and
reaches native READY; frozen composition installs the same identity through its
release source; missing catalog/source and hash/self-test failures retain distinct
safe UI/task diagnostics; the 67-Unit corpus rebuilds as `20+20+20+7`, publishes one
1024-dimensional generation, and reaches strict semantic readiness; a fake provider
rejection preserves safe HTTP/error/stage evidence without request bodies; focused,
full, package, and package-smoke gates pass before the coupled review resumes.

### Current gate

Sir authorized the commit followed by diagnosis. Commit
`b76a36e feat(knowledge): complete slice 03 operations and native OCR` contains the
completed Slice 03 Phase H scope. The Phase I findings and vector repair are recorded
in [runtime/index diagnostic evidence](../evidence/03-phase-i-runtime-index-diagnostic.md).
Sir then authorized the configurable/default-20 Embedding change and current-profile
update. The 67-Unit manual task succeeds, publishes a 1024-dimensional generation,
and explicit semantic retrieval returns results. The
[current OCR Service topology](../evidence/03-current-ocr-service-topology.md)
confirmed that process/runtime-generation boundaries were sound and isolated the
remaining source-composition and safe UI error-projection repair.

Sir explicitly started Phase I on 2026-07-23. Deployment now receives one
`PaddleOcrBundleSource`: development composes the exact generated local archive and
catalog, while frozen/default composition uses the catalog with the immutable release
origin. The shared deployment state machine retains outer size/SHA, safe extraction,
member-manifest, protocol, self-test, and atomic-generation gates. The setup task
projects only typed `knowledge_ocr_*` failures to translated Settings copy.

Index rebuild orchestration now retains safe `embedding_*` leaf failures and
content-free summaries in its existing task row/read model; interactive semantic
lookup still maps adapter failures to the Knowledge-domain availability contract. A
real source-mode install reached native `ready`, the focused Phase I cohort passed,
and the configured 67-Unit vector rebuild plus strict semantic query remain green.
The first fresh frozen smoke then exposed KB-D38: a staging-path self-test could
pass before the runtime moved beneath an overlong descriptive generation directory,
where Paddle could no longer resolve `.pdiparams`. Generation paths are now compact
content addresses, self-test runs on the final path before active-pointer
publication, and the rebuilt packaged native-OCR smoke passes.
See [Phase I implementation evidence](../evidence/03-phase-i-implementation.md).
Phase I is locally accepted; the final coupled review and any commit/publication
remain separately gated.
