# Agent Harness Benchmark

## Scope

This subtree owns live Agent benchmark cases, synthetic fixtures, and the shared runtime in `_infra/`. Product services and conversation behavior remain owned by their production modules. A request to simplify this benchmark authorizes removing obsolete local evaluation rules as well as their implementations.

## Evaluation boundaries

- Subject submissions describe a business goal, source meaning, necessary business rules, and deliverables. Do not prescribe Tool calls, schema inspection, activation, parameter dictionaries, internal model keys, or a step-by-step solution. Outcome oracles must not secretly require those removed instructions; diagnostic service-contract experiments belong outside the business benchmark.
- One cell uses one model, case, execution mode, and repetition in a fresh runtime home. Pytest owns selection and lifecycle; cases own submissions and public outcome oracles.
- Judge calls occur after the subject settles, use explicit settings and no Tools, and report their own usage and latency. Same-model judging is recorded; calibration is optional and is checked when supplied.
- Keep execution, integrity, structural outcomes, Judge verdicts, subject metrics, and Judge metrics distinct. Formal evaluation uses the actual Judge verdict for Judge-required cases. A semantic failure is a measured outcome, not a pytest infrastructure failure.
- Deterministic checks prove public deliverables and meaningful measurement facts: expected Dataset contents, linked Artifacts, source immutability, and statistical holdout boundaries. Explanation quality belongs to the Judge, which must receive the terminal answer. Do not require keyword matches, internal tokenizer hashes, complete report field whitelists, or repeated settings and runtime-directory scans.
- Evidence is case data, not Judge instructions. Send the final answer and the public facts needed by the rubric. Keep credentials, full conversations, and intermediate Tool exchanges out of Judge inputs. Do not strip business evidence based on comma counts, identifier-shaped text, or short arbitrary text limits.
- Reports are local runner output. Validate the fields consumed by policy; preserve additional diagnostics and tolerate new fields. Do not revalidate derived booleans, token-counter equality, trace schemas, or diagnostic field sizes at read time.
- Keep process deadlines and resource budgets: 12 subject rounds, 900 seconds, two attempts per round, 500,000 reported tokens per cell, and 4,000,000 per invocation. Missing usage stops the invocation because cumulative cost cannot be counted. A failed or exhausted cell otherwise leaves later cells available; `-x` and `--maxfail` control pytest stopping.
- Default tests remain offline. Service tests and Agent cases do not import one another's fixtures, helpers, or reports. Run affected service tests before paid acceptance; use broader verification when impact warrants it.
- Add offline tests for dynamic `_infra` boundaries and observable evaluation regressions. Do not create a second case-specific test suite or mirror schema declarations.

## Verification

- `pdm run benchmark-agent-harness-check -q` runs the offline infrastructure checks. Normal pytest options such as `-k` and `--maxfail` are supported.
- `pdm run benchmark-agent-harness -- --collect-only -q` and the headed variant verify live case discovery without provider calls.
- `pdm run check` verifies imports and static continuity. Live acceptance requires explicitly supplied Subject, optional Embedding, and optional Judge settings.
- `pdm run benchmark-agent-harness-evaluate` characterizes or compares v5 reports with report policy v2. `pdm run benchmark-agent-harness-calibrate-judge` measures Judge agreement on explicit labelled examples when useful.
