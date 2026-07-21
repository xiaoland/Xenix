# Slice 01 — Known-Findings Realignment

**State:** in progress — reopened on 2026-07-21 after an undersized closeout
**Authorized:** iterative design and implementation authorized by Sir

## Objective

Reconcile the complete currently known Knowledge Base delivery—not merely the Agent
Tool surface—with its accepted Import, Storage, and Tool designs. Slice 01 includes
KB-F01 through KB-F16, real semantic/hybrid retrieval, the accepted mode-selection
contract, and correction of Agent benchmarks so they grade the final answer rather
than an implementation trace.

The prior seven-row plan confused phases with slices. Those rows are now internal
work packages under this one Slice. Phase-level checkpoints are useful for safe
commits and verification, but only the entire cohort can close Slice 01.

## Scope and Authority

- **Import:** canonical-ready remains distinct from derivation/retrieval-ready;
  execution is service-owned and publication converges atomically.
- **Storage:** complete application envelope, immutable content addressing, stable
  migration edges, retrieval generations, and derived-index ownership.
- **Retrieval:** keyword, semantic, and hybrid modes are real selectable behaviors;
  unavailable capabilities fail honestly and `auto` selects only ready projections.
- **Agent:** one small canonical ToolResult, business-useful descriptions, integrated
  data-analysis methodology, path-safe and schema-honest execution.
- **Runtime/UI/delivery:** OCR readiness, translated service-owned UI state, packaged
  native/data exercises, and bounded diagnostics.
- **Evaluation:** benchmark semantic verdicts inspect final Assistant/Dataset/Artifact/
  chart deliverables. Tool Calls and ToolResults may diagnose execution, but cannot
  make the task pass.

Historical user state and canonical conversation values remain immutable unless a
separately designed compatibility migration is required. Existing user files are
never rewritten. Commits are checkpoints, not completion claims.

## Internal Sequence

```text
Phase A  Agent boundary checkpoint (implemented)
   |
   v
Phase B  semantic/hybrid research -> design -> implementation
   |                         |
   |                         +-> final-answer benchmark correction
   v
Phase C  canonical envelope and content identity
   v
Phase D  storage/migration/index-generation authority
   v
Phase E  service-owned import and atomic publication
   v
Phase F  OCR/UI/security/packaged delivery
   v
Phase G  Import <-> Storage <-> Tool global cross-review and outcome acceptance
```

This is a dependency hypothesis, not permission to preserve a bad boundary. Phase B
must record any storage/import prerequisite it discovers and either include the
minimum coherent prerequisite or revise the sequence explicitly.

## Phase A — Agent Boundary Checkpoint

Detailed record: [Agent boundary phase](01-agent-retrieval-contract.md).

Implemented and verified:

- provider input is `query + mode?`;
- one success value is `mode + results[{source, location?, excerpt}]`;
- internal document/unit/artifact/citation identities no longer cross the Tool;
- historical rich results replay without conversion;
- Knowledge methodology is integrated into analysis/preprocessing/modeling Skills;
- Knowledge-specific extra arguments, locator/source paths, and unexpected errors are
  bounded safely; and
- production composition/reopen/provider/Chatbot continuity is deterministic.

This phase deliberately left semantic/hybrid execution unavailable. That was a valid
checkpoint behavior, not fulfilment of Slice 01 or of the retrieval promise.

## Phase B — Semantic/Hybrid Retrieval and Outcome Benchmark

### Research questions

1. What is the stable `EmbeddingService` contract across user-controlled local or
   external providers: batching, dimensions, model identity, timeouts, and errors?
2. How should Docling-derived retrieval units be embedded without creating a second
   content authority or coupling Import to indexing?
3. How should LanceDB generations map to SQLite document/generation metadata, and how
   are stale, missing, or dimension-incompatible indexes excluded?
4. What are the measured semantics of `auto`, `keyword`, `semantic`, and `hybrid`?
   Which fusion method is explainable and robust for the MVP corpus?
5. How are Chinese and mixed-language queries evaluated, and what fixture set exposes
   lexical misses that semantic retrieval must recover?
6. Which configuration and health surfaces belong under the AI-service umbrella
   without reusing LLM authority?
7. What packaging/native dependencies does LanceDB add, and what is the smallest
   meaningful frozen-app exercise?

### Benchmark correction

- A case defines its final answer surfaces: terminal Assistant content and/or public
  Datasets, Artifacts, and charts.
- Deterministic facts and exact structured deliverables use deterministic checks.
- Insights, interpretation, or business advice use a bounded rubric and Judge only
  when deterministic checks cannot express the semantic requirement.
- Tool calls/results, retrieval mode, IDs, citations, and scores are never semantic
  pass criteria. They may appear only in diagnostic/execution metrics.
- The rainy-season case grades the exact restock Dataset and a grounded terminal
  answer containing the rule and SKU/quantity actions; the hidden rule plus input data
  makes successful retrieval behavior necessary without asserting a Tool trajectory.

### Design gate before implementation

Record the chosen embedding/provider abstraction, LanceDB schema/layout, generation
and publication sequence, hybrid ranking method, failure/fallback matrix, resource
limits, package impact, exact file surface, and black-box tests. Mentally replay at
least: lexical miss/semantic hit, exact-term hit, conflicting rankings, missing vector
generation, provider outage, model/dimension change, partial indexing, deletion or
refresh, and an `auto` call during degraded readiness.

## Remaining Phases

Phase C owns KB-F05/F06. Phase D owns KB-F07 and storage/index consequences
discovered by Phase B. Phase E owns KB-F02/F03/F04. Phase F owns KB-F08/F09 and the
remaining F10/F11/F12 seams. Phase G performs the promised global cross-review across
Import, Storage, and Tool; it is mandatory even if every local phase is green.

## Slice 01 Completion Criteria

- Every KB-F01..F16 row has current executable evidence and no “partial” remainder.
- Keyword, semantic, hybrid, and auto modes have truthful production behavior and
  measured retrieval value.
- Benchmarks grade final answer surfaces, not ToolResult payloads or prescribed traces.
- Import, canonical storage, retrieval projection, UI, and packaging owners agree in
  durable docs and code.
- Fresh and prior-state migrations, offline tests, packaged exercises, and relevant
  live outcome benchmarks pass or have an explicit external blocker.
- Sir is reminded and the global Import/Storage/Tool cross-review is completed before
  Slice 01 is marked verified.
