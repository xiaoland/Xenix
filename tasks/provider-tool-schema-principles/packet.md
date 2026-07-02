# Provider Tool Schema Principles

## Objective & Hypothesis

- Objective & Hypothesis: Distill generic provider-facing tool schema principles from the `model.metadata` refactor, but keep the code change conservative until the user explicitly confirms broader cross-tool adoption. Current hypothesis: the durable rule belongs in Agent Harness TDD first; concrete multi-tool schema slimming should happen only after explicit scope confirmation.

## Guardrails Touched

- Agent Harness owns provider-facing tool schemas and tool-call execution semantics.
- Execution-time authority remains in service handlers and downstream typed validators, not in duplicated schema taxonomies.
- Changes should preserve existing business behavior and avoid unconfirmed broad provider-facing schema relaxations.
- Ignore unrelated workspace changes.

## Verification

- Restore `src/xenix/services/agent/tools.py` to the confirmed `model.metadata`-only contract delta plus the pre-existing `analysis.graph` schema.
- Update `tests/test_agent_harness_first_slice.py` to cover only the confirmed contract.
- Run `pdm run agent-skills-generate` if skill-facing durable guidance changes.
- Run `pdm run pytest tests\test_agent_harness_first_slice.py -q`.

## Current State

- Current Understanding: The user confirmed the `model.metadata` contract change, but did not confirm the broader cross-tool schema slimming that landed in the second commit.
- User-Confirmed Constraints: Repair conservatively, restore the `analysis.graph` provider-facing schema, move the generic principle to TDD, and amend instead of creating a new commit.
- Active Mode or Transition Note: Execute conservative repair.
- Next Step: Stage the conservative repair files and amend the existing commit.

## Exploration Scaffold

- Perturbation: Preserve the confirmed `model.metadata` shape while removing unconfirmed collateral schema changes.
- Input Type: Constraint
- Governing Anchors: `AGENTS.md`, `docs/30-unit-tdd/agent-harness.md`, `src/xenix/services/AGENTS.md`.
- Impact Hypothesis: Keeping the durable principle in Agent Harness TDD preserves the design lesson without silently widening the code blast radius.
- Temporary Assumptions: The pre-existing `analysis.graph` explicit Vega structure and top-level unknown-key rejection should be restored unless the user later approves a separate simplification pass.
- Negotiation Triggers: Any future expansion from `model.metadata` into other provider-facing tool schemas needs explicit user confirmation first.
- Promotion Candidates: Durable provider-facing tool schema design principles in Agent Harness TDD only.
- Supporting Files: `src/xenix/services/agent/tools.py`, `tests/test_agent_harness_first_slice.py`, `docs/00-meta/implementation-taste.md`, `docs/30-unit-tdd/agent-harness.md`.

## Execution Notes

- Key findings:
  - The second commit overreached by applying schema-shape changes outside the user-confirmed `model.metadata` scope.
  - `analysis.graph` regressed because its provider-facing `spec` lost the explicit Vega structure that the current tests and prompt guidance relied on.
- Decisions made:
  - Keep the generic principle, but move it from framework meta docs into `docs/30-unit-tdd/agent-harness.md`.
  - Restore the broader tool schemas and handler strictness to their pre-second-commit shape.
  - Amend the existing commit instead of creating a new one.
- Verification outcomes:
  - `pdm run pytest tests\test_agent_harness_first_slice.py -q` passed with 19 tests.
- Final outcome: Conservative repair prepared; only the TDD-level principle promotion remains in the amended commit alongside the repaired task packet record.

## 2026-07-02 Exploration Refresh

- Current Slice: Execute
- Objective: Identify a user-confirmable next batch of provider-facing tool schema slimming work inside Agent Harness without silently changing execution semantics.
- Approved Execution Scope: `Option 1`, Batch A only, schema-only.

### Observed Schema Surface

- `model.metadata` is already the reference shape: split discovery from detail, no provider-side model-key enumeration, and no unnecessary alternate query knobs.
- `analysis.graph` is the largest remaining provider-facing schema by nested shape because `spec` still expands a Vega sub-schema even though runtime graph validation is service-owned.
- `data.query` and `data.transform` repeat a small nested `bindings` object shape and still close the top-level schema with `additionalProperties: False`.
- `data.feature.select`, `model.train`, `model.hyper_train`, and `model.task.query` are already top-level small, but still use closed schemas and sparse field descriptions.
- `model.apply` has a real nested input contract in `input_rows`; slimming here is lower-confidence because runtime typed validation genuinely depends on that shape.
- `data.peek`, `data.clean`, and `data.clean.metadata` are already small at the top level; most remaining change would be about closure or runtime tolerance, not token budget.

### Runtime Strictness Split

- Explicit runtime unknown-key rejection exists today in:
  - `data.peek`
  - `analysis.graph`
  - `analysis.lambda`
  - `data.clean`
  - `data.clean.metadata`
- The other listed provider-facing tools do not currently implement the same explicit top-level unknown-key rejection in their handlers.
- This means the next pass can be separated into:
  - schema-only slimming: reduce provider prompt surface without changing runtime acceptance behavior
  - runtime-tolerance change: intentionally stop rejecting unknown top-level keys where safe

### Recommended Candidate Batches

- Batch A, safest and highest signal:
  - `data.query`
  - `data.transform`
  - `data.feature.select`
  - `model.train`
  - `model.hyper_train`
  - `model.task.query`
- Batch B, high token payoff but needs explicit confirmation because it changes a previously sensitive surface:
  - `analysis.graph`
- Batch C, low payoff or semantically hotter:
  - `data.peek`
  - `data.clean`
  - `data.clean.metadata`
  - `model.apply`

### Proposed Mutation Rules For A First Approved Pass

- Keep tool behavior unchanged.
- Do not change handler unknown-key behavior unless separately approved.
- Prefer removing provider-side closure before touching nested payload structure.
- Only flatten nested objects when the service layer already owns the real validation contract.
- Do not touch `model.metadata` in this pass except for consistency fixes if strictly necessary.

### Next Negotiation Surface

- Option 1: Approve Batch A only, schema-only.
- Option 2: Approve Batch A plus `analysis.graph`, schema-only.
- Option 3: Approve a second pass later for runtime tolerance changes after schema-only verification.

## 2026-07-02 Option 1 Execution

- Address and Object:
  - `src/xenix/services/agent/tools.py`
  - `tests/test_agent_harness_first_slice.py`
  - `tasks/provider-tool-schema-principles/packet.md`
- State Diff:
  - From: Batch A tools still used closed provider-facing schemas with sparse field descriptions.
  - To: Batch A tools expose slimmer provider-facing schemas by removing schema-level closure and adding only short disambiguating descriptions.
- Blast Radius Forecast:
  - Agent Harness provider tool exposure payload shape
  - First-slice schema assertions
  - No expected runtime business-behavior change
- Invariants Check:
  - Do not change handler execution logic.
  - Do not change explicit runtime unknown-key behavior.
  - Do not touch `analysis.graph`, `data.peek`, `data.clean*`, `model.apply`, or `model.metadata`.
- Verification:
  - Run `pdm run pytest tests\\test_agent_harness_first_slice.py -q`.
- Verification Outcome:
  - `pdm run pytest tests\\test_agent_harness_first_slice.py -q` passed with 19 tests.
- Current Outcome:
  - Batch A schema-only slimming is implemented and verified.
  - Runtime handler semantics remain unchanged.
