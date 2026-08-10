# Working-Set and Ownership Map

## Default Turn Working Set

For any program turn, load only:

1. root `AGENTS.md`, the project working protocol, and this packet's `README.md` + `protocol.md`;
2. `decisions.md`, `open-questions.md`, and one active workstream packet;
3. only the referenced case rows and evidence IDs;
4. the governing durable owner/local `AGENTS.md`;
5. direct implementation files and focused tests for the approved state diff.

Do not preload the entire supplied corpus, all three workstreams, raw benchmark output, or broad repository history.

## Posture-Specific Additions

| Posture | Add to the default set |
| --- | --- |
| Explore | Candidate source seams, relevant evidence, and private material files needed for one question |
| Solidify | `program-plan.md`, `verification.md`, owner contracts, decision register, and proposed handshake |
| Execute | One approved handshake, its one linked implementation plan, exact files/symbols, focused tests, and active workstream packet |
| Diagnose | One Agent run summary, the independently executed service evidence for the corresponding planning risk, bounded logs/traces/DB queries, and the first suspected seam |

## Private Material Adoption Working Set

Load [the materials index](materials/README.md) and [on-demand adoption plan](materials/on-demand-adoption.md) only after one explicit real-scale, format, ablation, diagnosis, or manual-acceptance trigger. For recommendation/text, also load the narrower [RT adoption plan](materials/rt-on-demand-adoption.md). Then add one private adoption spec and only its selected original code/data. Do not add the entire corpus, co-located answers, supplied model artifacts, or unrelated chapters.

## Ownership Lanes

| Lane | Primary working set |
| --- | --- |
| Shared integration | `ml/types.py`, `ml/contracts.py`, `ml/evaluation.py`, `ml/registry.py`, `ml_service.py`, `ml_task_service.py`, trained-model metadata, Agent Tool inputs/projection |
| Vertical 01 domain | analysis profile/preparation seams, `ml/models/base.py`, `clustering.py`, future forecasting module, direct integration tests |
| Vertical 02 domain | `recommendation.py`, `text_analysis.py`, tokenization/preparation seams, direct integration tests |
| Cross-cut 00 evaluation | planning-only risk catalog, future service assets under `tests/**`, Agent assets under `benchmarks/agent_harness/**`, and benchmark scripts/policy/offline checks; no cross-tree imports or report dependency |
| Durable documents | PRD/Product TDD/Unit TDD only when the product promise or expensive cross-unit contract changes |

## Foundation Plan Working Sets

| Plan | Primary source set | Independent proof set |
| --- | --- | --- |
| Foundation 1 — Dataset profile and cleaning evidence | analysis profile, Dataset resolution, Agent profile Tool/composition/presentation, data analysis/preprocessing Skills | `test_analysis_profile.py`, `test_ml_foundation_profile_cleaning.py`, clean-room profile/cleaning fixture, then one independently invoked paid cleaning characterization |
| Foundation 2 — Group-safe preparation, evaluation, and lifecycle facts | ML types/contracts/evaluation/base model, supervised text seam, ML lifecycle/finalization, binding storage/migration, Agent ML projection/modeling Skill | registry/execution/storage/migration/Agent-projection tests and separate grouped train/apply fixtures |

The exact files and pass order are owned by [Foundation 1](implementation/F1-dataset-profile-cleaning.md) and [Foundation 2](implementation/F2-group-safe-preparation-evaluation.md). Do not load both execution sets in one implementation turn unless a verified cross-plan contract conflict requires it.

Optional full-material characterization follows the separate [on-demand adoption plan](materials/on-demand-adoption.md) and never enters either Foundation implementation working set or default CI automatically.

## CF Plan Working Sets

| Plan | Primary source set | Independent proof set |
| --- | --- | --- |
| CF-C — Clustering trustworthiness | catalog/capability and public Artifact seam, clustering base/adapters, evaluation/finalization, Agent clustering projection/Skill | separate service fixture/lifecycle selectors plus implemented, independently owned `ml.cluster_selection_v1` live case; verification before paid dispatch |
| CF-F — Native forecasting | temporal contracts/preparation/evaluation, forecasting adapters, lifecycle horizon apply, Agent forecast projection/Skill, packaged Statsmodels smoke | separate clean-room/metamorphic forecast selectors plus implemented, independently owned `ml.forecast_validation_v1` live case; offline/package verification before paid dispatch |

The exact scope, order, and stop conditions are owned by [IH-CF](handshakes/IH-CF.md), [CF-C](implementation/CF-C-clustering-trustworthiness.md), and [CF-F](implementation/CF-F-native-forecasting.md). Execute CF-C before CF-F because it establishes shared capability and public-Artifact references; the two proof sets and paid cases remain independent.

`IH-CF` is consumed. CF-C and CF-F implementation and objective verification are complete; bounded live results and diagnosis are in the [CF execution record](execution/CF-2026-08-09.md). The two independent benchmark modules each expose one live case, and headless/headed collect-only both contain the same ten cases. Reload this working set only for a reproduced CF regression, formal later acceptance, or an explicitly approved optimization.

## RT Plan Working Sets

| Plan | Primary source set | Independent proof set |
| --- | --- | --- |
| RT-R — Personalized recommendation ranking | recommendation evidence/preparation and analyzer, ranking taxonomy/contracts, lifecycle/result finalization, recommendation Tool projection/Skill | clean-room explicit-rating FIT → EVALUATE → APPLY service case plus an independently authored `ml.recommendation_ranking_v1` live case |
| RT-T1 — Multilingual preparation and grouped classification | tokenization/spec contracts, raw-text classification adapter, text preparation/leakage facts, lifecycle/Agent projection/Skills | independent bilingual preparation and grouped raw-text classification service cases plus `ml.text_grouped_classification_v1` |
| RT-T2 — Text discovery and retrieval evidence | raw-text clustering/topic/retrieval adapters, task-specific text evidence, result-contract materialization, Agent projection | independent discovery/relevance service cases plus `ml.text_topic_discovery_v1`; retrieval live is deferred pending relevance truth |

The exact scope and stop conditions are owned by proposed [IH-RT](handshakes/IH-RT.md) and the three linked implementation plans. Execute RT-R, then RT-T1, then RT-T2 so shared taxonomy/lifecycle/Agent files have one owner at a time. A plan loads only its clean-room proof assets; the [RT private material plan](materials/rt-on-demand-adoption.md) enters later only on an explicit characterization trigger.

## Conflict Hotspots

Serialize edits to these shared files; do not assign simultaneous owners:

- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/ml/evaluation.py`
- `src/xenix/services/ml/registry.py`
- `src/xenix/services/ml_service.py`
- `src/xenix/services/ml_task_service.py`
- `src/xenix/services/agent/tools.py`
- `src/xenix/services/agent/tool_inputs.py`
- Agent Skill catalogs and generated projections

Domain work may define a service/model type and its requirements independently, but public registration, shared result contracts, storage changes, and Agent projection are short serial integration steps.

## Diagnosis Working Set

A single failed live cell should be traceable through stable identities:

```text
case/run
-> thread/user message
-> provider sample
-> Tool admission/call/result
-> ML task queue/start/worker/finalize
-> Dataset/Artifact registration
-> assistant finalize
-> headed render
```

Prefer stable IDs, phase/status codes, bounded metrics, and durations. Do not copy raw rows, prompts, transcripts, credentials, local paths, or provider error bodies into the packet.
