# L2 Plan

## Stage Goal

Complete structural and process alignment to SVC v9.1, including full folder normalization, legacy deprecation, and guardrails that prevent drift.

## Why This Plan Exists

L2 is for teams that want strict governance consistency and are willing to absorb short-term migration cost to maximize long-term clarity.

## Scope

Included:

- Full adoption of canonical SVC folder schema under `docs/`.
- Full migration from `tasks/archive/` to top-level `tasks/` with archive separation.
- Full dynamic execution protocol in `AGENTS.md` with explicit confirmation gates.
- Add policy checks to discourage new docs in legacy locations.
- Introduce a minimal alignment pack under `docs/15-alignment/`.

Excluded:

- changing core app architecture in `src/xenix/` unless alignment reveals a real contract conflict

## Structural End State

- Durable docs:
  - `docs/10-prd/`
  - `docs/15-alignment/`
  - `docs/20-product-tdd/`
  - `docs/30-unit-tdd/`
  - `docs/40-deployment/`
- Volatile docs:
  - `tasks/active/`
  - `tasks/archive/`

Legacy end state:

- `docs/20-product-tdd/`, `docs/20-product-tdd/adr/`, `docs/40-deployment/`, `docs/40-deployment/`, and `tasks/archive/` become archived or are removed after migration completion.

## Proposed Phases

### Phase 1: Hardening Protocol

1. Rewrite `AGENTS.md` as an execution state machine with Mode A/B/C triggers and mandatory restatement blocks.
2. Add strict rule: ambiguous requests cannot modify durable docs or production code until Mode B confirmation.

### Phase 2: Full Doc Migration

1. Move durable docs into canonical numbered folders.
2. Move all task history into `tasks/archive/`.
3. Create `tasks/active/` for current exploratory and execution plans.

### Phase 3: Governance Enforcement

1. Add a lightweight check script (or CI job) to fail on:
   - new files in deprecated legacy folders
   - missing restatement section in execution task docs
2. Add contributor checklist entries that mirror v9.1 promotion rules.

### Phase 4: Drift Prevention

1. Add alignment pack artifacts:
   - domain glossary
   - operation taxonomy
   - UI/service target map for common change operations
2. Review once per milestone and prune stale docs.

## Deliverables

- fully normalized `docs/` structure
- fully normalized `tasks/` structure
- strict `AGENTS.md` protocol
- migration and deprecation report
- automated drift check

## Acceptance Criteria

- No active planning in `tasks/archive/`.
- No new durable truth added outside canonical SVC folders.
- Ambiguous prompts consistently start in Mode A artifacts under `tasks/active/`.
- Promotion of truths from tasks to durable docs is explicit and auditable.

## Risk Profile

- High migration cost and review churn
- Highest alignment fidelity
- Best fit for teams prioritizing governance rigor over short-term throughput


