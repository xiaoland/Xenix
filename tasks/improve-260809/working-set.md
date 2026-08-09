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
| Execute | One approved handshake, exact files/symbols, focused tests, and active workstream packet |
| Diagnose | One Agent run summary, the independently executed service evidence for the corresponding planning risk, bounded logs/traces/DB queries, and the first suspected seam |

## Ownership Lanes

| Lane | Primary working set |
| --- | --- |
| Shared integration | `ml/types.py`, `ml/contracts.py`, `ml/evaluation.py`, `ml/registry.py`, `ml_service.py`, `ml_task_service.py`, trained-model metadata, Agent Tool inputs/projection |
| Vertical 01 domain | analysis profile/preparation seams, `ml/models/base.py`, `clustering.py`, future forecasting module, direct integration tests |
| Vertical 02 domain | `recommendation.py`, `text_analysis.py`, tokenization/preparation seams, direct integration tests |
| Cross-cut 00 evaluation | planning-only risk catalog, future service assets under `tests/**`, Agent assets under `benchmarks/agent_harness/**`, and benchmark scripts/policy/offline checks; no cross-tree imports or report dependency |
| Durable documents | PRD/Product TDD/Unit TDD only when the product promise or expensive cross-unit contract changes |

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
