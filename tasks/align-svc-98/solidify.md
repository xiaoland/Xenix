# Execution Task

## Pre-Execution Restatement

- Target:
  - Align Xenix Native repository governance and documentation to verified upstream SVC `v9.7`.
  - Keep the topology as single-repo.
  - Clean stale historical documentation that conflicts with the `v9.7` owner model and task model.
- State and context:
  - Current Xenix already has a partial SVC shape across `docs/`, `tasks/`, and local `AGENTS.md`.
  - The current baseline references are split across `v9.1` and `v9.3`.
  - The declared task topology and actual task topology diverge.
  - The documented `check-svc-docs` command currently points to a missing script.
- Operation:
  - Update repository-level SVC alignment artifacts.
  - Normalize task-layer documentation and historical task placement strategy.
  - Remove or rewrite stale SVC historical carry-overs.
  - Remove the obsolete `check-svc-docs` command surface from repository docs and project scripts.
- Scope included:
  - Root and docs-level SVC references.
  - Task-layer topology and task workspace conventions.
  - Historical SVC framework snapshots or layer-map docs that currently conflict with `v9.7`.
  - Governance docs and project config that still mention `check-svc-docs`.
- Scope excluded:
  - Application feature changes under `src/xenix/`.
  - UI renaming, service refactors, or ML workflow redesign.
  - Multi-repo support.
  - Migration or deletion work under `ml/`.
- Invariants:
  - `tasks/` remains the volatility buffer.
  - Durable truths stay inside their canonical owners.
  - Local `AGENTS.md` files near risky seams remain first-class guidance.
  - `docs/15-alignment/` keeps coordination grammar only.
  - Single-repo remains the active operating model.
  - Existing app architecture boundaries remain intact unless a documented owner boundary needs wording cleanup.
- Likely affected files:
  - `README.md`
  - `CONTRIBUTING.md`
  - `pyproject.toml`
  - `docs/README.md`
  - `docs/SVC-LAYER-MAP.md`
  - `docs/_SVC_v9_1.md`
  - `docs/00-meta/README.md`
  - `docs/15-alignment/README.md`
  - `docs/15-alignment/operation-taxonomy.md`
  - `docs/15-alignment/target-map.md`
  - `docs/20-product-tdd/README.md`
  - `docs/40-deployment/development.md`
  - `tasks/README.md`
  - `tasks/templates/exploration.md`
  - `tasks/templates/execution.md`
  - `tasks/templates/result.md`
  - task directories that need normalization under `tasks/`
- Uncertainty:
  - Whether `docs/_SVC_v9_1.md` should be deleted outright or replaced by a short local pointer model.
  - Whether historical task folders should be migrated into `tasks/archive/` or preserved with a compatibility note.

## Proposed Change Set

1. Refresh top-level and docs-level SVC baseline references to `v9.7`.
2. Replace stale layer-map and embedded framework carry-over with a `v9.7`-aligned local routing description.
3. Normalize `tasks` documentation and physical topology to one coherent model.
4. Clean obsolete historical task/doc artifacts that conflict with the chosen model.
5. Remove the obsolete `check-svc-docs` command surface.

## Expected Durable Destinations

- Product meaning changes:
  - none expected
- Technical governance and routing truth:
  - `docs/00-meta/`
  - `docs/15-alignment/`
  - `docs/20-product-tdd/` only if a cross-unit technical boundary truly changed
- Runtime / contributor workflow truth:
  - `README.md`
  - `CONTRIBUTING.md`
  - `docs/40-deployment/`
- Volatile migration reasoning and cleanup rationale:
  - `tasks/align-svc-98/`

## Confirmation Needed Before Execution

- Baseline confirmed: `SVC v9.7`
- Operating model confirmed: `single-repo`
- Pending execution confirmation:
  - proceed with the change set above

## Plan

1. Update repository-level SVC references and owner-routing docs.
2. Normalize task-layer docs and decide the historical task migration shape.
3. Remove obsolete command references and clean stale artifacts.

## Verification

- Command:
  - not yet requested
- Expected:
  - documentation and task topology stay coherent after the cleanup
- Observed:
  - pending execution

## Promotion Notes

- Durable truth candidates:
  - exact `v9.7` owner map adopted by Xenix
  - normalized task topology for this repository
  - removal of obsolete SVC command references
- Keep in task only:
  - cleanup sequencing
  - migration rationale for historical leftovers
