# Agent Harness Benchmark

Applies to live cases, synthetic fixtures, and `_infra/` in this subtree. Production behavior remains owned by production services.

- Before changing cases, judging, budgets, or reports, read the [benchmark unit design](../../../docs/30-unit-tdd/agent-harness-benchmark.md).
- Prompts describe business goals and constraints, not Tool sequences or parameter recipes. Oracles verify public outcomes rather than secretly restoring removed procedural requirements.
- Keep normal tests offline. Live acceptance uses explicitly supplied Subject, optional Embedding, and optional Judge settings.
- Do not add automated tests of benchmark infrastructure. `pdm run benchmark-agent-harness -- --collect-only -q` verifies discovery without provider calls; use saved evidence or explicit live runs for outcome checks. Shared contributor guidance owns broader verification.
