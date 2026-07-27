# Knowledge Base Follow-up — Contract Realignment

**Status:** Completed and closed by Sir on 2026-07-24
**Opened:** 2026-07-21
**Posture:** All admitted Knowledge follow-up slices and the final coupled review are
accepted; multimodal work remains parked outside this completed task

## Objective

Keep the Knowledge Base implementation aligned with Product TDD, Unit TDD, local
`AGENTS.md`, implementation taste, and the accepted workstream designs while new
product findings are discussed and admitted as coherent slices. Preserve the Slice
01 and Slice 02 evidence, and design Slice 03 around a stable native local-OCR
bundle, a responsive Workspace, truthful status, and one cross-owner task query
plane rendered locally as `Task queue`. Multimodal retrieval remains a separately
admitted follow-up.

## Guardrails

- `LLMConversationService` retains one canonical ToolResult value. Provider replay
  and Chatbot projection copy that value; no hidden provenance result or second
  semantic representation may be introduced.
- Knowledge-domain rows may retain internal identity, but a Tool crosses only the
  smallest value needed for the Agent's next operation.
- Import, retrieval derivation, UI presentation, canonical content, and conversation
  state retain their documented owners. A passing vertical demo cannot merge those
  authorities implicitly.
- Existing migration edges, user-owned files, Artifact identity, and canonical
  conversation history are treated as potentially deployed state until proven
  otherwise.
- Tests must prove the governing contract and real delivery boundary. A test that
  merely asserts the current implementation shape is not completion evidence.
- A new finding does not block the current phase unless it invalidates that phase's
  contract or authority boundary. Related Knowledge findings join the active slice
  through an explicit Impact Handshake revision; they are never silently hidden or
  promoted into artificial subsystem-sized slices.
- Only the active phase authorizes product-code changes. Each phase records its own
  Impact Handshake, preplay, verification, and remaining debt while the Slice-level
  scope stays intact. Commits still require Sir's explicit command.
- Completion of one phase is not completion of its slice. The final
  Import/Storage/Tool/UI/OCR/runtime/release/index review was required because task
  execution, document lifecycle, index generations, settings, release transport,
  and Agent evidence are coupled; Sir accepted that coupled result on 2026-07-24.

## Verification

- Every reported issue receives an ID, governing contract, current-code evidence,
  impact, and disposition in [the compliance audit](compliance-audit.md).
- Rejected claims remain recorded with the evidence that disproved them; issue count
  is not optimized at the expense of accuracy.
- The corrected Agent boundary is explicit in
  [the single-ToolResult contract](tool-result-contract.md).
- Before implementation, the repair plan must name exact authority changes,
  migration strategy, lifecycle convergence point, package exercise, and tests.
- Relative packet links and whitespace are checked after each material update.

## Current Truth

- The 2026-07-21 findings remain the historical audit baseline; every KB-F01..F17
  row has locally executable closure evidence. Sir closed Slice 01 on 2026-07-22.
- TXT, DOC/DOCX, PPT/PPTX, PDF, JPEG, and PNG enter one extensible probe/normalize/
  route/parse/canonical path. PPTX uses bounded OOXML validation and Docling; legacy
  PPT uses a named LibreOffice-to-PPTX conversion profile before the same parser.
  Import still owns a durable queue and stops at immutable canonical-ready;
  independent derivation alone publishes bounded Units and FTS readiness.
- SQLite schema v23 owns lifecycle, current pointers, deterministic Units, retrieval readiness,
  and observable Knowledge index rebuild tasks. Source/canonical bytes are
  content-addressed; LanceDB is an immutable rebuildable semantic projection bound
  to current SQLite generations.
- The Tool has one canonical `mode/results[{source, location?, excerpt}]` value,
  validates its advertised schema, exposes truthful selectable modes, and is taught
  as part of the three data-analysis Skills rather than a standalone task.
- Local PaddleOCR readiness, translated service-driven queue UI, independent
  Embedding settings, real Import-backed benchmark preparation, frozen Knowledge
  exercises, and DOC fidelity/UI visual evidence are in place.
- Slice 02 now implements the next product cohort: process-isolated import execution
  and readable logs, a logical-document list, Knowledge-owned settings, explicit
  index compatibility/rebuild controls, and the carried final-answer repair.
- Benchmark outcome authority is the Agent's final Assistant/Dataset/Artifact/chart
  deliverable. Tool Calls and ToolResults are diagnostic telemetry, not semantic
  success evidence.
- On 2026-07-22 the carried benchmark was diagnosed as an overly narrow
  final-answer oracle, not missing retrieval or Agent reasoning. After admitting
  bounded equivalent Chinese wording and Unicode-minus normalization—while still
  requiring the rule, inventory-gap/non-positive logic, and exact Dataset—the
  configured `kimi/kimi-k2.6` and independent Embedding provider passed the isolated
  live cell with semantic and integrity verdicts true.
- Current JPEG/PNG and document-picture import preserves multimodal source content,
  but retrieval is text-only: OCR, extracted table text, and surrounding text may be
  searched; image-only meaning is not embedded or delivered to the Agent.
- Slice 03 is now the active cohort. It records the existing-but-
  incompatible PaddleOCR runtime, Python/pip deployment fragility, synchronous
  Workspace status scans, unified task-queue direction, footer hierarchy, and legacy
  unbounded Unit projection evidence. Sir selected official Paddle Inference C++ and
  the disposable compatibility spike now passes on PaddleOCR `v3.7.0` + Paddle
  Inference `3.3.0` with the selected PP-OCRv6 medium models. It also records the
  required upstream-config guard, complete dynamic DLL closure, sizing/performance
  baseline, and remaining worker-protocol proof. The packet defines the exact native
  build, release, migration, service, UI, and acceptance sequence.
- The 2026-07-23 global rerun opened KB-D26..KB-D31. Sir admitted them as one Phase F
  repair cohort. The capability/provider graph, PDF page evidence states, frozen
  projection snapshot, deterministic Unit identities, OCR verification/provenance,
  Windows Job Object ownership, and route-complete real native OCR acceptance now
  pass locally.
- The final review then opened KB-D32 and KB-D33: the intended presentation formats
  were omitted from the active registry, and the Workspace has no drag-and-drop
  entry. Sir started their single Phase G cohort; source/full/frozen/public-fixture
  acceptance now passes locally.
- A real post-Phase-G Workspace import of the named 53 MB PPTX failed in the
  production spawned-import topology. Database, task-log, CAS, and direct-parser
  evidence prove that the source snapshot is intact and that failure occurs only
  after `parsing_started`. Phase G acceptance bypassed the production nested-process
  topology. Phase H now makes the spawned Import worker the sole Docling isolation
  boundary, distinguishes safe worker outcome/stage/diagnostic fields and parent
  launch/timeout/crash/result failures, exercises the real spawned named-PPTX path,
  and presents the Workspace-local label `Task queue` / `任务队列`.
- The resumed review opened KB-D36–D37. Source-mode local OCR setup fails before
  download because neither a runtime catalog nor release origin is composed into
  `run_dev.py`; the UI then discards the structured failure. The original text-vector
  task failed before LanceDB publication because its configured 64-item request
  exceeded the selected provider/model's 20-item limit; semantic/index wrapping
  collapsed the safe provider error into `knowledge_semantic_unavailable`. Sir then
  authorized a configurable default of 20. The service default and current profile
  now use 20; a manual 67-Unit rebuild publishes a 1024-dimensional generation in
  four requests and strict semantic retrieval succeeds.
- Phase I now gives OCR deployment one explicit bundle-source contract. Development
  composes the exact generated local catalog/archive; frozen builds retain the same
  deployment state machine with an immutable release source. Typed, content-free OCR
  setup failures reach Knowledge Settings, and index tasks preserve safe Embedding
  error codes plus actionable summaries without provider bodies. A real source-mode
  install reached the selected native generation's `ready` state. Frozen acceptance
  then exposed and repaired a final-path-only native model failure: compact
  content-addressed generation paths are now self-tested before active publication,
  and the rebuilt packaged native-OCR smoke passes.
- After Phase I commit `ac283b1`, KB-D39 was confirmed. The document query is about
  17.53 ms, but the first strict vector status costs about 2168.22 ms and the atomic
  Workspace snapshot withholds the list until both complete. The viewport meanwhile
  rendered the empty-library copy before any result existed. Phase J now uses
  independent document/footer projections, explicit viewport states,
  stale-while-refresh, and lifecycle/request generations. Its diagnosis is recorded in
  [its diagnostic evidence](evidence/03-phase-j-workspace-loading-diagnostic.md).
- Sir then admitted document removal as Phase K. `KnowledgeService` remains
  retrieval-only; a new lifecycle service performs one guarded SQLite cutover,
  reference-aware Artifact/CAS cleanup, vector invalidation/rebuild notification,
  and typed busy rejection. The Workspace exposes the operation only through the
  exact item's right-click menu and translated destructive confirmation. Its design
  is recorded in
  [the document-removal design](evidence/03-phase-k-document-removal-design.md).
- Phases J/K pass focused, complete repository (`633 passed, 3 skipped`), app-entry
  (`58 passed`), static, fresh package, and frozen-smoke gates. Frozen smoke proves
  spawned import/derivation/lookup, removal, lookup absence, original-file
  preservation, and same-SHA fresh re-import. See
  [implementation evidence](evidence/03-phase-j-k-implementation.md).

## Closure

Sir accepted the complete Knowledge follow-up result and authorized its commit on
2026-07-24. All admitted slices are closed. Multimodal retrieval remains a parked
future task. The next product workstream is the separately scoped v1.2.0 release.

## Packet Map

- [Compliance audit and disposition matrix](compliance-audit.md)
- [Corrected single-ToolResult contract](tool-result-contract.md)
- [Ongoing discussion register](discussion-register.md)
- [Slice ledger and phase map](slices/README.md)
- [Slice 01 — complete known-findings realignment](slices/01-known-findings-realignment.md)
- [Slice 01 / Phase A — Agent retrieval contract checkpoint](slices/01-agent-retrieval-contract.md)
- [Slice 01 / Phase B — Semantic/hybrid retrieval](slices/01-semantic-hybrid-retrieval.md)
- [Slice 01 / Phases C–G — local closeout](slices/01-phases-c-g-closeout.md)
- [Slice 02 — Knowledge operations, workspace, and index control](slices/02-knowledge-operations-workspace-indexes.md)
- [Slice 03 — Local OCR, Workspace responsiveness, and Knowledge operations](slices/03-local-ocr-workspace-operations.md)
- [Slice 03 — Detailed implementation plan and Impact Handshake](slices/03-implementation-plan.md)
- [Slice 03 evidence — local OCR runtime research](evidence/03-ocr-runtime-research.md)
- [Slice 03 evidence — native OCR and operations implementation](evidence/03-native-runtime-implementation.md)
- [Slice 03 evidence — legacy Unit/PPTX diagnostic](evidence/03-pptx-unit-diagnostic.md)
- [Slice 03 evidence — OCR deployment and vector-task diagnosis](evidence/03-phase-i-runtime-index-diagnostic.md)
- [Slice 03 evidence — current OCR Service topology](evidence/03-current-ocr-service-topology.md)
- [Slice 03 evidence — Phase I implementation and acceptance](evidence/03-phase-i-implementation.md)
- [Slice 03 evidence — Workspace loading diagnosis](evidence/03-phase-j-workspace-loading-diagnostic.md)
- [Slice 03 evidence — document-removal design](evidence/03-phase-k-document-removal-design.md)
- [Slice 03 evidence — Phase J/K implementation and acceptance](evidence/03-phase-j-k-implementation.md)
- [Parked follow-up — multimodal retrieval design](slices/02-multimodal-retrieval.md)
- [Original Knowledge Base delivery packet](../knowledge-base/README.md)
