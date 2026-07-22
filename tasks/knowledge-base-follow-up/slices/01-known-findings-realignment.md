# Slice 01 — Known-Findings Realignment

**State:** closed by Sir on 2026-07-22 with the Phase B outcome residual carried to Slice 02
**Authorized:** iterative design and implementation authorized by Sir

## Objective

Reconcile the complete currently known Knowledge Base delivery—not merely the Agent
Tool surface—with its accepted Import, Storage, and Tool designs. Slice 01 includes
KB-F01 through KB-F17, real semantic/hybrid retrieval, the accepted mode-selection
contract, and correction of Agent benchmarks so they grade the final answer rather
than an implementation trace.

The prior seven-row plan confused phases with slices. Those rows are now internal
work packages under this one Slice. Phase-level checkpoints are useful for safe
commits and verification, but only the entire cohort can close Slice 01.

## Scope and Authority

- **Import:** canonical-ready remains distinct from derivation/retrieval-ready;
  execution is service-owned, the promised TXT/DOC(X)/PDF/JPEG/PNG routes are real,
  and publication converges atomically.
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
Phase D  storage and migration stabilization
   v
Phase E  service-owned import and atomic publication
   v
Phase F  OCR/UI/security/packaged delivery
   v
Phase G  Import <-> Storage <-> Tool global cross-review and outcome acceptance
```

This is a dependency hypothesis, not permission to preserve a bad boundary. Phase B
owns the semantic derived-generation publication contract and the minimum fixed
migration edge needed to add it. It must not move embedding/LanceDB work into Import
or claim that the later Canonical, Import, and historical-migration repairs are done.

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

At the Phase A checkpoint, semantic/hybrid execution was deliberately unavailable.
That was a valid historical checkpoint behavior, not fulfilment of Slice 01 or of the
retrieval promise; Phase B has since replaced it with real configured execution.

## Phase B — Semantic/Hybrid Retrieval and Outcome Benchmark

Detailed record: [Semantic/hybrid retrieval phase](01-semantic-hybrid-retrieval.md).

### Decisions and implementation checkpoint

1. `EmbeddingService` is independent from LLM settings and freezes one validated
   operation across query and document batching, dimensions, identity, timeout, and
   bounded errors.
2. SQLite Knowledge Units remain content authority; LanceDB stores only immutable
   `unit_id -> vector` generations and Import receives no Embedding/Lance dependency.
3. SQLite v18 generation metadata plus a bounded Lance manifest bind library, corpus,
   profile, dimensions, row count, path, and ordered unit IDs. Stale or malformed
   generations are never eligible.
4. `keyword` is SQLite FTS, `semantic` is exact flat cosine, `hybrid` is deterministic
   RRF, and `auto` falls back only on expected semantic unavailability.
5. The rainy-season fixture is a lexical paraphrase and its submission explicitly
   requests semantic retrieval, while its oracle remains the final exact Dataset and
   grounded answer—not the Tool trace.
6. The AI settings UI has a separate Embedding card backed by the same explicitly
   injected settings authority used by production Agent composition.
7. Installed Windows/Python 3.14 Lance write/rename/reopen/search is proven. The
   meaningful frozen-app exercise remains Phase F and is not inferred from the wheel.

### Benchmark correction already applied at the Phase A checkpoint

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

Phase B keeps that oracle boundary unchanged and adds an explicit external Embedding
settings seam. Two dedicated live cells ran on 2026-07-22: both completed with the
exact Dataset and full integrity, but failed the grounded final-answer check. It does
not move ToolResult inspection back into semantic acceptance.

### Recorded design gate and evidence

The detailed Phase B record contains the chosen embedding/provider abstraction,
LanceDB schema/layout and manifest, generation/publication sequence, hybrid ranking,
failure/fallback matrix, resource bounds, package impact, file surface, preplay, and
black-box evidence. Its focused verification passed 95 tests. Phase B is a verified
implementation checkpoint only; it does not close Slice 01.

## Local Closeout

Phases C–G are locally verified under the shared
[closeout record](01-phases-c-g-closeout.md): schema v20 and immutable canonical
identity, independent bounded derivation, durable service-owned imports, the exact
MVP format registry, OCR/UI/schema/path/package closure, and the final
Import/Storage/Tool topology review. All KB-F01..F17 rows therefore have local
closure evidence.

The only unmet acceptance item at closure was Phase B's real-provider rainy-season
Agent outcome. Provider settings were proven; the stable final-answer omission is
carried as Slice 02 finding `KB2-F01`. The exact Dataset/terminal-answer oracle remains
the authority and Tool telemetry still cannot provide semantic credit.

## Slice 01 Completion Criteria

- Every KB-F01..F17 row has current executable evidence and no “partial” remainder.
- Keyword, semantic, hybrid, and auto modes have truthful production behavior and
  measured retrieval value.
- Benchmarks grade final answer surfaces, not ToolResult payloads or prescribed traces.
- Import, canonical storage, retrieval projection, UI, and packaging owners agree in
  durable docs and code.
- Fresh and prior-state migrations, offline tests, packaged exercises, and relevant
  live outcome benchmarks pass or have an explicit external blocker.
- Sir is reminded and the global Import/Storage/Tool cross-review is completed before
  Slice 01 is marked verified.

The global review was completed locally. Sir closed Slice 01 on 2026-07-22 and
admitted the next product cohort as Slice 02. This closure is a scope decision, not a
claim that the two failed final-answer cells passed.
