# Slice 03 — Local OCR, Workspace Responsiveness, and Knowledge Operations

**State:** Closed by Sir on 2026-07-24
**Opened:** 2026-07-22
**Scope rule:** this is one admitted finding cohort with internal phases, not one
slice per UI, runtime, storage, or migration change

## Objective

Make the Knowledge Workspace fast and operationally truthful. Replace the fragile
runtime-installed Python/PaddleOCR environment with a versioned local OCR runtime
bundle; distinguish missing, incompatible, repairable, and ready OCR states; expose
import, derivation, and index activity through one query plane rendered as
`Task queue`; and move global Knowledge status into a quiet footer below the
document list. Let the user remove one selected logical document without deleting
the original source file or leaving searchable/indexed application state behind.

The target is retrieval usefulness, not a general recovery or audit platform. Task
and status metadata remain only as rich as needed to keep Knowledge content
searchable and user operations understandable.

## Admitted Findings

| ID | Finding | Current evidence | Target outcome |
| --- | --- | --- | --- |
| KB3-F01 | A previously installed local PaddleOCR runtime is shown as not installed. | The unreleased embedded Python runtime used incompatible health semantics, and its private model root was empty while PP-OCRv6 models were written to the user's global `.paddlex` directory. Sir authorized deleting that private sidecar before the native spike. | Do not migrate the unreleased sidecar. Start from verified native runtime/model identities and keep truthful missing, corrupt/incompatible, installing, failed, and ready states. |
| KB3-F02 | The Python + pip sidecar installer is too fragile for a desktop product. | Setup downloads embedded Python and pip, resolves a large Python dependency graph at runtime, warms models, and replaces the private runtime in place. | Build and distribute a hash-verified official Paddle Inference C++ runtime bundle with no user-machine Python or pip resolution. |
| KB3-F03 | Opening the Knowledge Workspace blocks the UI for several seconds. | A fresh Workspace import loads the heavy Knowledge pipeline; construction/show invokes three refreshes; every refresh synchronously recomputes semantic status from all current Unit bodies, and the visible window repeats it every second. | Show the window shell immediately; load documents/status asynchronously from bounded metadata; never scan content bodies or start subprocesses on the UI thread. |
| KB3-F04 | Index builds are observable in storage but absent from the user-visible queue. | `knowledge_index_task` persists trigger/status/phase/error, while `KnowledgeImportQueueDialog` reads only import and linked derivation attempts. | Replace Import Queue with a modeless `Task queue` that presents import, content preparation, and index activity without merging their storage authorities. |
| KB3-F05 | Global OCR/index status occupies the top of the Workspace and has excessive visual weight. | Description, OCR status, and index status appear before the toolbar and document list. | Remove the description and render a small palette-muted footer below the document list for OCR, keyword, and text-vector state. |
| KB3-F06 | Persisted legacy Units can violate the current 8,000-character projection bound. | The current user database has 116 Units over about 86 million characters, including one about 4.27 million characters; current `bound_knowledge_units` does enforce 8,000 characters, so the rows predate the present projection contract. | Reset the authorized local Knowledge fixture, reproduce with the named PPTX, and determine whether current derivation is bounded; define a retrieval-projection compatibility/re-derivation rule rather than silently trusting legacy rows. |
| KB3-F07 | The intended PPT/PPTX input formats are absent from the implemented product registry. | Docling 2.114.0 exposes a native PPTX backend and the 53 MB product fixture already converts successfully; legacy PPT requires LibreOffice. Current registry/worker/tests reject both by policy. | Register complete PPTX and PPT→PPTX capability paths with source-format provenance, OOXML/CFB validation, package evidence, and bounded searchable derivation. |
| KB3-F08 | The Knowledge Workspace cannot import by drag and drop. | The current dialog exposes only `QFileDialog`; neither the document list nor Workspace shell accepts drops. | Add a Workspace-local drop adapter and converge drop/file-picker input on one ordered, deduplicated submission path without moving admission authority into a widget. |

## Accepted Direction

1. Process isolation remains correct; runtime installation by Python/pip does not.
   The selected topology is an Xenix-owned official Paddle Inference C++ worker plus
   explicitly versioned model assets. MVP distributes them in one verified archive;
   their identities remain separate so later model updates need not redefine the
   worker protocol.
2. `not_installed` is reserved for an absent runtime. Minimum product states are
   `checking`, `ready`, `not_installed`, `repair_required`, `installing`, and
   `failed`. Safe reason codes may refine them without becoming user copy.
3. Workspace presentation opens before service refresh completes. Expensive OCR
   health checks, index integrity checks, provider operations, and Unit-body reads
   are forbidden from the UI thread.
4. The Workspace `Task queue` is one presentation/query plane over separate import,
   derivation, and index authorities. It does not introduce a generic task
   super-table or pretend every task has identical retry/cancel/log capabilities.
5. The Workspace description is removed. A compact footer below the content list
   projects global OCR/keyword/vector status from a cached, service-owned DTO.
6. Sir authorized deleting Knowledge-specific data from the local Xenix runtime and
   re-testing with
   `tests/.mock-data/2026半年度工作汇报（品牌营销）.pptx`. This diagnostic use does
   not restore PPTX to the current MVP import promise.
7. The Slice 02 decision to keep Import Queue import-specific is superseded for
   Slice 03. Slice 02 history and evidence remain unchanged.
8. Sir's 2026-07-23 clarification supersedes the earlier PPT/PPTX non-goal. PPTX
   uses Docling directly; PPT uses the same class of explicit LibreOffice
   normalization boundary as DOC, targeting PPTX. Historical evidence remains
   labelled according to the scope that existed when it was produced.
9. File picker and drag-and-drop are presentation inputs to one Workspace submission
   operation. A drop adapter may extract local file URLs and provide affordance, but
   it does not probe files, enqueue tasks, or become a second allowlist authority.
10. Document removal is one service-owned lifecycle command, not a widget-side row
    deletion and not a new Agent Tool. MVP hard-removes the selected document's
    Xenix-owned lifecycle/retrieval lineage, invalidates affected vector generations,
    and reclaims only content whose lack of references can be proven. It never
    mutates or deletes the user-selected source file and introduces no undo,
    tombstone, recovery, or audit product.

## Target Topology

```text
Knowledge Workspace
  |-- immediate window shell
  |-- async document/status snapshot ----> bounded SQLite metadata
  |-- remove selected document ----------> document-lifecycle command
  |                                         |-- SQLite/FTS cutover
  |                                         |-- vector invalidation/rebuild
  |                                         `-- owned-byte reclamation
  |-- Task queue -----------------------> task-feed query service
  |                                         |-- import attempts
  |                                         |-- derivation attempts
  |                                         `-- index tasks
  `-- footer ----------------------------> cached Knowledge status DTO

OCR service
  |-- versioned native worker executable
  |-- versioned model pack(s)
  |-- bounded stdin/stdout or file protocol
  `-- manifest + atomic bundle activation

No Python/pip resolution, content scan, provider call, or OCR subprocess startup is
required to make the Workspace visible.
```

"Single-file deployment" means one downloaded, unpack-and-run archive from the user's
perspective. Official Paddle Inference on Windows still requires the executable plus
several DLLs, so the product does not claim a physically single executable. Model
weights retain a separate logical identity inside the MVP archive.

## Internal Phase Plan

| Phase | Purpose | Exit evidence |
| --- | --- | --- |
| A — Research and fixture diagnosis | Compare official Paddle deployment paths and mature offline OCR projects; select the native backend; safely reset local Knowledge data and reproduce current Unit derivation with the authorized PPTX. | **Complete.** Official Paddle Inference C++ selected; source-linked matrix, reset inventory, and bounded current-PPTX derivation recorded. |
| B — OCR runtime bundle | Implement the approved worker/model bundle, explicit state machine, repair boundary, and packaged activation. | **Implemented.** Clean native build, deterministic catalog/archive, persistent-session golden run, and production-service install/activate/offline-recognize evidence pass. |
| C — Fast status and Workspace shell | Remove heavyweight UI import seams and synchronous/repeated status scans; introduce bounded async/cached status projection. | **Implemented.** Schema v22 projection metadata, stale legacy invalidation, lightweight format seam, and latest-generation asynchronous Workspace snapshot tests pass. |
| D — Task queue and Workspace hierarchy | Add the unified task-feed DTO/dialog, footer, and remove description. | **Implemented.** Import/content/index query plane, asynchronous modeless dialog, logical-document list, muted footer, and complete bilingual catalogs are in place. |
| E — Acceptance and global review | Exercise retrieval after repair/rebuild and review Import, Storage, Tool, UI, index, and runtime boundaries together. | **Global rerun performed.** It opened KB-D26–D31, which Sir admitted as one Phase F convergence repair. |
| F — Structural convergence repair | Replace branch/race/status/process gaps with provider, snapshot, runtime-generation, and process-tree models; then run route-complete acceptance. | **Implemented and locally accepted.** Focused/full/package/native/live evidence passes; only the final Sir cross-workstream review remains. |
| G — Presentation import completion | Admit PPT/PPTX through the provider graph and let the Workspace accept the same files through picker or drag/drop. | **Implemented and locally accepted.** Real PPT/PPTX/encrypted/named-fixture, picker/drop, full-suite, frozen worker, and package smoke evidence passes. |
| H — Production import topology | Remove the redundant untested nested Docling boundary, preserve safe failure stages, prove the real spawned path with the named PPTX, and simplify the Workspace-local queue label. | **Implemented and locally accepted.** One spawned Import process now runs Docling directly; structured safe failure results, real named-PPTX spawn, frozen package exercise, and bilingual `Task queue` coverage pass. |
| I — Runtime distribution and vector failure truth | Make local OCR setup executable in each supported application composition and preserve actionable, content-free Embedding failure evidence through the index task boundary. | **Implemented and locally accepted.** Batch size defaults to 20; safe Embedding failures reach index tasks; local/release OCR sources share one deployment state machine. Compact content-addressed generations are self-tested at their final path, and real source plus rebuilt frozen native-OCR acceptance pass. |
| J — Progressive Workspace loading | Stop optional footer/index work from withholding the document list, and distinguish loading from a truly empty Library. | **Implemented and locally accepted.** Independent projections, explicit viewport states, stale-while-refresh, request/lifecycle generations, UI/i18n, full, package, and smoke gates pass. |
| K — Document removal | Remove one selected logical document, all of its searchable/application-owned lineage, and incompatible vector generations without touching the user's source file. | **Implemented and locally accepted.** Guarded lifecycle cutover, owner-aware cleanup, vector convergence, item context menu, focused/full/package/frozen-smoke evidence pass. |

Phases are implementation checkpoints only. Slice 03 closes as one cohort.

## Resolved Phase A Decisions

- Native backend: official Paddle Inference C++, selected by Sir.
- Capability: general text detection + recognition only; PP-StructureV3/layout stays
  outside Slice 03.
- Distribution: one optional immutable Xenix-hosted archive containing runtime DLL
  closure plus default model pack; runtime/model identities remain distinct.
- Upgrade: no legacy Python compatibility exists; native bytes are staged,
  hash-verified, self-tested, and atomically activated. Future corrupt/incompatible
  native generations use `repair_required`.
- Projection compatibility: record an explicit retrieval projection version and
  bounded fingerprint/count metadata, then re-derive stale generations before
  indexing.

## Phase A Evidence and Recommendation

- [Local OCR runtime research](../evidence/03-ocr-runtime-research.md) records Sir's
  selection of an Xenix-owned official Paddle Inference C++ worker. ONNX/ncnn remain
  research alternatives only and cannot replace the selected backend without a new
  handshake. PaddleOCR-json/Umi-OCR are architecture references, not binary
  dependencies.
- The installed runtime occupies about 1.01 GB and did not contain its claimed model
  inventory under the app-owned model root. PaddleX instead populated about 139 MB of
  `PP-OCRv6_medium_det`/`PP-OCRv6_medium_rec` under `%USERPROFILE%\.paddlex`.
  The native spike therefore uses those exact model identities as its fidelity
  baseline but moves their bytes under an explicit Xenix-owned model pack.
- [Legacy Unit/PPTX diagnostic](../evidence/03-pptx-unit-diagnostic.md) completed the
  authorized reset. The exact 53 MB PPTX now produces 67 Units, 1,509 total
  characters, a 377-character maximum, no Base64 Unit, and no 8,000-character bound
  violation. The historical 4.27-million-character row was a picture data URI.
- The recommended deployment identity is a native runtime bundle plus a separate
  model-pack identity, atomically activated after hash verification and self-test.
  One native process is scoped to one import attempt and initializes the model once
  for all OCR-routed pages.
- The authorized disposable native spike built PaddleOCR `v3.7.0` with Paddle
  Inference `3.3.0`, fixed the upstream sample's invalid mandatory read of optional
  `DetResizeForTest.resize_long`, and ran full PP-OCRv6 medium detection/recognition
  successfully. It establishes a 488,641,489-byte uncompressed runtime+model sizing
  baseline and records dynamic MKL/OpenMP closure requirements. The exact pins,
  output, latency, memory, and remaining protocol proofs are in the linked evidence.
- Sir authorized the exact Impact Handshake, and Phases B–D now implement it. The
  clean native build and real deployment exercise are recorded in
  [native runtime implementation evidence](../evidence/03-native-runtime-implementation.md).

The exact code, migration, release, UI, and acceptance sequence is now specified in
[the Slice 03 detailed implementation plan](03-implementation-plan.md).

## Mutation Boundary

Sir authorized the recorded Phase B–F product-code, migration, native build,
packaging, UI, test, and durable-document implementation on 2026-07-22. The
PPT/PPTX and Workspace-drop Phase G scope was identified and explicitly started by
Sir on 2026-07-23. The Phase H runtime diagnosis and task-packet update are complete;
Sir explicitly started its product-code repair, which is now implemented and locally
accepted. Sir explicitly started Phase I on 2026-07-23. Its Embedding
default/current-profile repair, safe index-error projection, explicit OCR
bundle-source composition, typed setup failure path, and real development install
are implemented and locally accepted.

None of these permissions authorizes publication, release, a second destructive
local-data reset, or multimodal scope. The completed Phase H scope is committed as
`b76a36e`; subsequent commits remain separately gated.
Sir explicitly started Phase J/K. Their product code, tests, translations, frozen
smoke, and durable contracts are implemented and locally accepted. Commit and
publication remain separately gated.

## Cross-slice Review Gate

Slice 02 was locally delivered and committed before this slice opened. The carried
Import/Storage/Tool/UI/runtime review ran on 2026-07-23 and confirmed the repaired
authority topology while finding KB-D26–D31. Sir admitted and locally verified their
Phase F repair. That final review exposed KB-D32–D33 and paused for Phase G. Phase G
now passes locally, but a real Workspace re-import exposed the production topology
gap recorded in
[Phase H evidence](../evidence/03-phase-h-import-failure.md). Its
repository/package acceptance passes. The resumed review then exposed the
source-mode OCR deployment and vector-task failure recorded in
[Phase I diagnosis](../evidence/03-phase-i-runtime-index-diagnostic.md).
[Phase I implementation evidence](../evidence/03-phase-i-implementation.md) records
the accepted repair. KB-D39 and KB-D40 are now implemented and locally accepted as
Phases J/K; their evidence is in
[Phase J/K implementation evidence](../evidence/03-phase-j-k-implementation.md).
Sir accepted the final Import/Storage/Tool/UI/OCR/runtime/release/index coupled
result and closed Slice 03 and the complete Knowledge follow-up task on 2026-07-24.
