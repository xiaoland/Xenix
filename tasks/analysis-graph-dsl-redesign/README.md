# Analysis Graph DSL Redesign

## Objective & Hypothesis

- Objective: redesign `analysis.graph` so its purpose remains chart generation, while the Agent uses a compact declarative visualization DSL instead of choosing from a small fixed operation enum.
- Hypothesis: the best target is an engine-first contract: use a real visualization grammar/runtime where feasible, and let Xenix own only dataset binding, safety policy, execution bounds, artifact registration, and packaging integration. A Xenix-owned DSL should be a fallback, not the default, because every custom grammar adds LLM cognitive load.

## Prompt

- User plans to redo the existing `analysis.graph`.
- The new shape should think like `data.query`: an expressive DSL is accepted, service code validates and bounds execution, and the Agent has more freedom without needing many rigid operations.
- User has investigated Vega-Lite style declarative visualization DSLs and wants alternatives considered against Xenix's stack and data-mining/business-analysis practice.
- This is a large task; keep a poly-file task packet and update it during discussion.

## Input Classification

- Type: `Intent`.
- Current mode: `Explore`, moving toward `Solidify` only after high-level details are confirmed.
- No implementation should start until the user explicitly says to start.

## Current Durable Owners

- Product scope: `docs/10-prd/product-scope.md`
- Runtime boundary: `docs/20-product-tdd/runtime-boundaries.md`
- Agent Harness contract: `docs/30-unit-tdd/agent-harness.md`
- Service code likely affected after confirmation:
  - `src/xenix/services/analysis_graph.py`
  - `src/xenix/services/agent/tools.py`
  - `src/xenix/services/artifact_service.py` only if artifact formats or previews change
  - `tests/test_analysis_graph.py`
  - Agent harness exposure/schema tests if tool shape changes

## Packet Files

- `exploration.md`: current facts, topology, unknowns, and candidate directions.
- `dsl-options.md`: compared visualization DSL options and current working recommendation.
- `sanitizer-policy.md`: proposed Xenix policy layer for accepting Vega-Lite specs without turning `analysis.graph` into a custom DSL.
- `solidify-review.md`: multi-perspective review from product demand, technical reality, boundaries, failure modes, and sub-agent code mapping.
- `impact-handshake.md`: pre-implementation state diff, blast radius, invariants, and verification plan to confirm with the user.
- `discussion-log.md`: running discussion notes and decision ledger.

## Guardrails Touched

- Agent-facing schema must remain compact, provider-friendly, and aligned with existing visualization grammar when possible.
- Tool execution must use registered datasets, not arbitrary local paths.
- Generated charts must be bounded by rows, columns, category count, output size, and rendering time.
- Artifact identity and preview/open behavior remain service-owned.
- Desktop packaging must remain offline-capable and PyInstaller-friendly.
- Existing `analysis.profile`, `analysis.lambda`, `data.query`, and `data.transform` responsibilities should not be blurred.
- `analysis.graph` should not become a data transformation tool. Data shaping, joins, cleaning, and materialized transforms stay with `data.clean`, `data.query`, and `data.transform`.

## Verification

- This packet is discussion-only.
- Current verification is evidence capture from code/docs and primary vendor docs.
- Future implementation verification should include schema contract tests, validation rejection tests, artifact registration tests, image rendering smoke tests, and packaged smoke coverage if new rendering dependencies are added.

## Smallest Confirmation Needed

- Confirmed: first provider-facing schema should be `{dataset_id, spec}`.
- Confirmed: no compatibility is needed for the old `{operation, params}` contract.
- Confirmed: Vega-Lite transform features do not need special prohibition solely for orthogonality; the Agent can use tools orthogonally, while Xenix still owns registered-dataset access and rendering bounds.
- Confirmed: proceed with first spike around `vl-convert-python`.
