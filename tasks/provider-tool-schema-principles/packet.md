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
