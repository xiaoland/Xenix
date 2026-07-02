# Model Metadata Two-Stage Contract

## Objective & Hypothesis

- Objective & Hypothesis: Refactor `model.metadata` into a two-stage contract so model discovery stays lightweight and parameter inspection becomes an explicit single-model follow-up. Current hypothesis: the existing mixed list/detail shape increases prompt bloat and raises model-selection and parameter hallucination risk.

## Guardrails Touched

- Agent Harness owns provider-facing tool schemas and execution semantics for `model.metadata`.
- ML model catalog remains the single source of truth for canonical model keys, role schemas, capabilities, and parameter schemas.
- `model.train` and `model.hyper_train` payload shapes stay unchanged.
- Skill source files under `src/xenix/services/agent/skills/` must stay aligned with the generated static skill catalog.

## Verification

- Update `tests/test_agent_harness_first_slice.py` to cover:
  - no-filter validation failure;
  - lightweight directory mode without parameter schemas;
  - single-model detail mode with default `param_schema`;
  - `include_param_grid_schema=true` implying `param_schema`.
- Run `pdm run agent-skills-generate`.
- Run targeted pytest for `test_agent_harness_first_slice.py`.

## Current State

- Current Understanding: `model.metadata` now separates lightweight directory discovery from single-model detail inspection. Its provider-facing schema is reduced to `model_family`, `model_key`, and `include_param_grid_schema`.
- User-Confirmed Constraints: No-filter calls must fail and force narrower queries first.
- Active Mode or Transition Note: Verification complete.
- Next Step: Report the implemented contract and verification results.

## Exploration Scaffold

- Perturbation: Split discovery from detail inspection while preserving existing model catalog authority.
- Input Type: Constraint
- Governing Anchors: `AGENTS.md`, `docs/00-meta/implementation-taste.md`, `docs/30-unit-tdd/agent-harness.md`, `src/xenix/services/AGENTS.md`, `src/xenix/services/ml/AGENTS.md`.
- Impact Hypothesis: Tool outputs become smaller and more deliberate; LLMs choose models from lightweight summaries before opening single-model parameter detail.
- Temporary Assumptions: Keeping `model_keys` as a backward-compatibility alias is acceptable only if it cannot recreate multi-model schema dumps.
- Negotiation Triggers: If changing to single `model_key` would break a broader persisted/runtime contract outside Agent Harness, pause and confirm.
- Promotion Candidates: Durable Agent Harness contract note for two-stage model metadata usage.
- Supporting Files: `src/xenix/services/agent/tools.py`, `tests/test_agent_harness_first_slice.py`, `docs/30-unit-tdd/agent-harness.md`, `src/xenix/services/agent/skills/xenix-data-modeling/`.

## Execution Notes

- Key findings:
  - The highest-risk stale contract copies lived in Agent Harness unit docs and generated skill resources, not in Python comments.
  - Keeping hidden backward compatibility for `model_keys` and `include_param_schema` inside the handler avoids brittle internal breakage while removing them from the provider-facing schema.
- Decisions made:
  - No-filter calls fail rather than returning the full catalog.
  - Extra provider-facing query knobs such as `problem_kind`, `evaluation_kind`, `model_task_kind`, and `capability` were removed from the `model.metadata` schema.
  - `additionalProperties: false` was removed from the `model.metadata` provider schema.
- Verification outcomes:
  - `pdm run agent-skills-generate` passed and regenerated the static skill catalog.
  - `pdm run pytest tests\test_agent_harness_first_slice.py -q` passed with 19 tests.
- Final outcome: `model.metadata` now enforces a two-stage contract with a minimal three-field provider-facing schema across implementation, tests, and modeling-skill documentation.
