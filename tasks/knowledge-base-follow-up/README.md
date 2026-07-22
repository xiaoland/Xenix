# Knowledge Base Follow-up — Contract Realignment

**Status:** Slice 01 closed; Slice 02 locally verified, global cross-review pending
**Opened:** 2026-07-21
**Posture:** implement the approved Slice 02 phases; multimodal work is parked

## Objective

Keep the Knowledge Base implementation aligned with Product TDD, Unit TDD, local
`AGENTS.md`, implementation taste, and the accepted workstream designs while new
product findings are discussed and admitted as coherent slices. Preserve the Slice
01 evidence, carry its known benchmark residual honestly, and design Slice 02 around
observable Knowledge operations, a useful document workspace, explicit index
lifecycle control. Multimodal retrieval remains a separately admitted follow-up.

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
- Completion of one phase is not completion of its slice. At the end of Slice 02,
  perform another global Import/Storage/Tool/UI/runtime review because task execution,
  document lifecycle, index generations, settings, and Agent evidence are coupled.

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
- TXT, DOC/DOCX, PDF, JPEG, and PNG enter one extensible probe/normalize/route/parse/
  canonical path. Import owns a durable queue and stops at immutable canonical-ready;
  independent derivation alone publishes bounded Units and FTS readiness.
- SQLite schema v21 owns lifecycle, current pointers, Units, retrieval readiness,
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

## Next Step

Review the global Import/Storage/Tool/UI/runtime topology with Sir before closing
Slice 02 or declaring the Knowledge Base workstreams coherent. Multimodal retrieval
stays outside this slice. Sir authorized organizing the completed work into separate
implementation and documentation commits on 2026-07-22.

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
- [Parked follow-up — multimodal retrieval design](slices/02-multimodal-retrieval.md)
- [Original Knowledge Base delivery packet](../knowledge-base/README.md)
