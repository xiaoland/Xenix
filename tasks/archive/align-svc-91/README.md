# Align SVC v9.1 Plans

## Task

- Target framework: `docs/_SVC_v9_1.md`
- Goal: align the repository documentation and execution protocol with SVC v9.1 using plans grounded in the current codebase and docs model.

## Current Baseline (Observed)

### Code system

- Desktop app is implemented in `src/xenix/` with a layered split across `ui/` and `services/`.
- Core runtime and storage behavior already exists and is test-backed (`tests/`).
- Service boundaries already match several SVC ideas (explicit contracts, local runtime ownership, and test-first verification for critical behavior).

### Documentation system

- Current durable docs use:
  - `docs/20-product-tdd/`
  - `docs/20-product-tdd/adr/`
  - `docs/40-deployment/`
  - `docs/40-deployment/`
- Volatile planning currently lives in `tasks/archive/issue-*/` (L0-L3 + RESULT style).
- There is no top-level `tasks/` workspace yet, which is a key SVC v9.1 expectation.
- `AGENTS.md` is concise and practical, but does not yet codify the v9.1 dynamic protocol (Mode A/B/C + task-first ambiguity handling).

## Gap Summary Against SVC v9.1

1. Task layer location mismatch:
   - SVC v9.1 expects volatile planning in top-level `tasks/`.
   - Current repo keeps it under `tasks/archive/`.
2. Execution protocol mismatch:
   - SVC v9.1 requires dynamic mode selection and a pre-execution restatement anchor.
   - Current `AGENTS.md` does not define this yet.
3. Layer naming mismatch:
   - SVC v9.1 recommends `10-prd`, `15-alignment`, `20-product-tdd`, `30-unit-tdd`, `40-deployment`.
   - Current model is semantically close but named differently.

## Plan Set

- `L0-PLAN.md`: low-risk bridge with minimal structural churn.
- `L1-PLAN.md`: progressive alignment with canonical SVC naming and migration shims.
- `L2-PLAN.md`: strict alignment with full move/rename and policy enforcement.

## Suggested Default

- Start with `L1-PLAN.md`.
- It gives strong v9.1 alignment while controlling migration risk and avoiding abrupt documentation breakage.


