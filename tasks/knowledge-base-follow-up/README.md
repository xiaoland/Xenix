# Knowledge Base Follow-up — Contract Realignment

**Status:** active iterative remediation — Slice 01 reopened and in progress
**Opened:** 2026-07-21
**Posture:** accept new findings continuously; design, implement, and verify one bounded phase at a time inside Slice 01

## Objective

Reconcile the current uncommitted Knowledge Base implementation with the repository's
Product TDD, Unit TDD, local `AGENTS.md`, implementation taste, and the accepted
workstream designs. Keep one place for Sir's additional findings, distinguish
functional evidence from engineering completion, and produce a repair design that
can be implemented without creating new authorities or rewriting contracts around
the shortcut.

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
  contract or authority boundary. Related Knowledge findings join the active Slice
  through an explicit Impact Handshake revision; they are never silently hidden or
  promoted into artificial subsystem-sized slices.
- Only the active phase authorizes product-code changes. Each phase records its own
  Impact Handshake, preplay, verification, and remaining debt while the Slice-level
  scope stays intact. Commits still require Sir's explicit command.
- Completion of one phase is not completion of Slice 01. After the Import, Storage,
  and Tool workstreams are all reconciled, perform one global cross-workstream review
  because their lifecycle, index, and Tool contracts are coupled.

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

- The current worktree demonstrates a useful end-to-end path: six accepted file
  extensions, source-mode Docling import, a real local PaddleOCR deployment, one
  production Agent benchmark pass, and a canonical `knowledge.lookup` ToolResult.
- That evidence does **not** establish repository-compliant completion. The earlier
  completion claim is withdrawn.
- At audit opening, the Tool's single value followed the correct Conversation path but
  was over-specified. Phase A has since reduced new results to the agreed
  `mode/results` value without introducing a second result plane.
- Confirmed deviations include import/retrieval boundary collapse, UI-owned daemon
  execution, non-atomic publication, canonical-envelope/CAS identity gaps, mutable
  migration-edge behavior, insufficient packaged exercises, weak OCR readiness
  validation, untranslated dynamic UI state, and path-safety seams.
- The green test suite largely proves the implemented shortcut is internally
  consistent. Several tests encode that shortcut and therefore cannot serve as
  independent evidence that the intended design was respected.
- No product file was modified during the 2026-07-21 compliance audit.
- Sir corrected the slice granularity on 2026-07-21: the full KB-F01..F16 cohort is
  Slice 01. The Agent-facing contract is only a verified internal phase; real
  semantic/hybrid retrieval and every other known remediation remain in the same
  open Slice.
- Benchmark outcome authority is the Agent's final Assistant/Dataset/Artifact/chart
  deliverable. Tool Calls and ToolResults are diagnostic telemetry, not semantic
  success evidence.

## Next Step

Create a checkpoint commit for the completed Agent-boundary phase, then execute
Phase B in [the active Slice 01 plan](slices/01-known-findings-realignment.md): research
and weigh semantic/hybrid retrieval, record its design/preplay, and only then
implement it. Continue admitting related findings without fragmenting this cohort.

## Packet Map

- [Compliance audit and disposition matrix](compliance-audit.md)
- [Corrected single-ToolResult contract](tool-result-contract.md)
- [Ongoing discussion register](discussion-register.md)
- [Slice ledger and phase map](slices/README.md)
- [Slice 01 — complete known-findings realignment](slices/01-known-findings-realignment.md)
- [Slice 01 / Phase A — Agent retrieval contract checkpoint](slices/01-agent-retrieval-contract.md)
- [Original Knowledge Base delivery packet](../knowledge-base/README.md)
