# B0 Research — 2026-08-09

## Benchmark Control Surface

- `pdm run benchmark-agent-harness` and the headed variant delegate selected case modules to pytest.
- Explicit settings paths, model selection, output directory, source path, and ordinary pytest selection exist.
- Repetition, seed, hard sampling/time budget, Judge calibration, and report-level acceptance commands do not exist.
- Omitting `--model` runs every configured subject model. The approved B0 design changes this to exactly `default_fq_model_key`; model selection is not a Harness benchmark matrix axis.
- Each cell gets an isolated runtime and persisted schema-v4 report.
- Pytest fails only on no cell, persistence failure, or non-completed execution. Semantic fail, integrity false, and Judge unavailable can still exit zero.

## Current Report Evidence

The report separates:

- execution and stable failure kind;
- semantic verdict/checks;
- integrity verdict/checks;
- Judge status/verdict/independence/scores/reason codes/metrics;
- subject latency, sampling rounds, tokens, Tool/result counts, retry count, derived outputs, and terminal shape;
- fixture/settings/Judge/repository identity.

It intentionally omits transcript, raw Tool payload, raw fixture rows, paths, credentials, endpoints, and raw provider/Judge errors.

## Historical Cost/Latency Evidence

Prior bounded live evidence on Kimi K2.6 recorded:

- Knowledge restock: roughly 19k subject tokens and 33–66 seconds, semantic/integrity pass.
- Regional chart: roughly 18–24k subject tokens and 48–69 seconds, semantic/integrity pass.
- Complex cleaning failure: roughly 240k subject tokens and 1,102 seconds, integrity pass but semantic fail.
- Later provider `429` attempts produced no product-quality evidence.

Therefore a matrix-wide estimate based only on average successful cases is unsafe. Current post-run token observation is not a hard cap. B0 must run one process/cell, refuse a thirteenth sampling round, terminate the process at 900 seconds, stop between cells, and use secondary reported-token limits.

## Service-Test Portfolio

- `pdm run test -- --collect-only -q` collected 45 cases on 2026-08-09.
- The existing proof-portfolio decision admits new pytest cases only for material Xenix outcomes not better proven by types, constraints, mature libraries, smoke, packaging, benchmarks, or observability.
- Crossing 50 requires a portfolio/architecture review; 100 remains the hard ceiling.
- The old 1,219-line ML execution test mixed many lifecycle branches and was deliberately removed. Its useful public path was Dataset registration -> role binding -> ML task/worker -> trained model/evaluation -> apply -> registered result.
- The new material cases meet the admission rule, but should return as a small business-scenario portfolio rather than resurrecting model-by-model or branch-by-branch tests.

## Fixture and Licensing Finding

- Textbook source and its transformed/sampled derivatives remain non-committable while rights are unresolved.
- Clean-room synthetic fixtures can encode the same business invariants without copying bytes or reference text.
- Default CI must not search for, download, or silently skip an explicitly requested external fixture.
- Full/private cases require source-tree, admitted-projection, evaluator, dependency, and run identity binding.

## Settings Finding

No reusable benchmark subject settings snapshot currently exists in the normal Xenix runtime config directory. B0 therefore defines policy around an explicit external snapshot rather than assuming an installed UI configuration. Exact model/provider selection is an execution input, not a product-design question.

## Ownership and Ordering Finding

The approved boundary keeps service black-box code and execution under `tests/` and paid live Agent benchmark code and execution under `benchmarks/agent_harness/`. There is no shared executable case kernel or runtime service prerequisite. Development guidance and a manual paid CI workflow express `service job success -> Agent job dispatch` without passing code, fixtures, reports, or verdicts between jobs.
