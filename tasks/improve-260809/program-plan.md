# Program Topology and Sequence

## Topology

```mermaid
flowchart LR
    M["Ignored source corpus"] --> Q["Private case qualification"]
    Q --> C["Planning-only business-risk map"]
    C --> S["tests/: service black-box cases"]
    C --> A["benchmarks/agent_harness/: paid live cases"]
    S -. "development / CI dispatch order only" .-> A
    S --> SR["Independent service evidence"]
    A --> AR["Independent Agent evidence"]
    AR --> H["Headless public outcomes"]
    H --> U["Headed UI outcome"]
    SR --> D["Post-run first-divergence diagnosis"]
    AR --> D
    D --> O["Exact preprocessing / Skill / Tool / orchestration change"]
    O --> C
```

Only the business risk and planning vocabulary are shared. Service tests and Agent benchmarks own separate code, fixtures, evaluators, commands, and reports. The dotted edge is workflow control only: CI does not dispatch a paid benchmark job after a red service job, while a directly invoked benchmark neither checks nor reads service results. The Agent subject sees only admitted business inputs; its evaluator privately owns answers, labels, future windows, reference code, and scoring rules.

## Two Verticals and One First Cross-Cut

| Lane | Product question | First delivery |
| --- | --- | --- |
| Cross-cut 00 — Baseline, acceptance, diagnosis | Where does a real business task first fail, and what is the smallest justified change? | Qualified cases, service/Agent evidence separation, before/after runs, acceptance policy, attribution |
| 01 — Foundation, clustering, forecasting | Can Xenix prepare data safely, assess segment quality, and forecast through an honest temporal workflow? | Shared profile/evaluation facts, split-aware semantics, trustworthy clustering, first native forecast workflow |
| 02 — Recommendation and text | Can Xenix produce and evaluate user-level ranking and defensible multilingual text results? | Popularity/cold-start + collaborative Top-K; language-aware text preparation and task-specific quality evidence |

## Sequence

```mermaid
sequenceDiagram
    participant B0 as "Cross-cut 00: B0 baseline"
    participant V1 as "Vertical 01"
    participant D1 as "Diagnosis loop"
    participant V2 as "Vertical 02"
    participant D2 as "Diagnosis loop"

    B0->>B0: Qualify private evidence and define planning risk IDs
    B0->>B0: Install single-model live runner safety and Agent policy
    B0-->>V1: Independent test/benchmark ownership and acceptance contract
    V1->>V1: Implement and pass service integration tests
    V1-->>D1: CI dispatches the corresponding independent live Agent case
    D1->>D1: Locate first divergence and optimize only that seam
    D1-->>V2: Stable shared preprocessing/result contracts
    V2->>V2: Implement and pass service integration tests
    V2-->>D2: CI dispatches the corresponding independent live Agent case
    D2->>D2: Attribute failures, compare quality/performance/cost, run ablations
```

Cross-cut 00 is therefore a bracket around product work, not a third product vertical or final cleanup phase.

## Authorization Points

1. `IH-B0`: benchmark safety, independent Agent cases, acceptance policy, guidance/CI ordering, and private qualification; no service-test or production behavior change.
2. `IH-F`: bounded profile/evaluation/result and split-aware preparation contracts.
3. `IH-CF`: clustering trustworthiness and first forecast workflow.
4. `IH-RT`: recommendation ranking and text quality workflow.
5. `IH-O<n>`: one reproduced benchmark failure and its exact optimization seam.

No `IH-O<n>` is written in advance. Logs, traces, and DB evidence determine whether the owner is data preparation, ML service, Tool boundary, Agent orchestration, UI, or evaluator infrastructure.
