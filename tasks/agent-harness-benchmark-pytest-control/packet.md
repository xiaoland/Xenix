# Agent Harness Benchmark Pytest Control Migration

## Objective

Make `benchmarks/agent_harness/` the authoritative home for Agent Harness
benchmark cases. Keep generic execution, evaluation, contracts, and pytest
adapter code in `_infra/`; make each case one pytest-collected benchmark module
rather than an implementation plus a duplicated case-specific test file.

## Guardrails

- `pdm run test` remains offline and does not collect or invoke paid providers.
- Explicit benchmark runs use pytest as the controller; CLI is at most a thin
  adapter into the pytest session.
- A semantic failure remains a measured benchmark outcome, not a pytest
  infrastructure failure. Invalid setup, runtime failure, or failed report
  persistence fails the selected pytest item.
- Retain only dynamic boundary proof that static typing, schema validation,
  fixture validation, or ordinary compiler checks cannot establish. Do not add
  case self-tests for static declarations.
- Preserve the V2 public result schema, evidence privacy boundary, isolated
  cell lifecycle, real-provider path, and explicit judge configuration.

## Verification

- Focused offline dynamic-infrastructure tests pass without a network call.
- `pdm run benchmark-agent-harness -- --collect-only` discovers the selected
  case modules without provider access.
- An explicit dry-run/controlled pytest invocation validates option routing;
  live Kimi is only run if still necessary after migration.
- `pdm run test`, `pdm run check`, and `git diff --check` pass.

## Current Truth

- `benchmarks/agent_harness/` now contains the case modules, their fixtures,
  local guidance, and `_infra`; `tests/` retains only generic dynamic boundary
  proof.
- The thin benchmark command delegates collection, selection, and execution
  lifecycle to the repository's existing pytest wrapper. There is no case
  registry or a second control loop.
- `scripts/run_pytest.py` remains the source of PDM-backed pytest invocation
  and isolated `--basetemp`; `pyproject.toml` explicitly makes the repository
  root importable and compile-checks `benchmarks/`.

## Outcome

The migration is implemented and verified through collection-only, controlled
no-provider routing, one live Kimi subject/judge cell, full offline regression,
compile verification, and diff hygiene. Future benchmark expansion adds one
case module plus fixtures; it does not add a case registry or a duplicate test
file.
