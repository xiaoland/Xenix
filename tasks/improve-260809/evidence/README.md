# Evidence Index

Evidence records observations; it does not authorize or define product behavior.

| ID | Observation | Provenance |
| --- | --- | --- |
| E-001 | Repository baseline: 45 ordinary tests pass; headless/headed benchmark each collect the same 3 cases; no live baseline was run | read-only commands on 2026-08-09 |
| E-002 | Clustering has five tabular models but weak quality/stability/profile evidence and an inconsistent reusable-apply story | source and product-contract inspection |
| E-003 | Recommendation has one item-similarity implementation; native forecasting is absent; text has four analyzer workflows with preparation/evaluation gaps | source and registry inspection |
| E-004 | Ordinary test coverage no longer directly exercises real ML lifecycle outcomes, while benchmark infrastructure already supports isolated outcome inspection | test/benchmark audit |
| E-005 | The ignored corpus contains complete cases for cleaning, leakage-safe preparation, clustering, recommendation, forecasting, and bilingual text, plus colocated answers and unsafe Joblib artifacts | corpus inventory and safe parse checks |
| E-006 | Representative clustering, recommendation, forecasting, and text scripts run under the current environment; exact results are evaluator-private and version-sensitive where applicable | safe local execution with bytecode and GUI plotting disabled |
| E-007 | Current benchmark settings default to every configured subject model when `--model` is omitted; report schema v4 records rich separate channels but pytest does not gate semantic/integrity failure | runner/plugin/source inspection |
| E-008 | Historical successful live cases used about 18–24k subject tokens and under 70 seconds, while a failed complex cleaning case used about 240k tokens and 18 minutes | prior bounded benchmark evidence |
| E-009 | Current ordinary suite collects 45 cases; the documented portfolio rule requires architecture review when additions cross 50 | `pdm run test -- --collect-only -q` and proof-portfolio decision |
| E-010 | Current live runner has no hard sampling-round or outer cell-process deadline; reported usage is available only after provider responses, so a portable strict token pre-admission cap cannot be claimed | runner, Harness loop, and provider/settings inspection |
| E-011 | B0 now runs one pinned subject model per cell behind 12-round, 900-second, 500k-cell, 4m-invocation, two-attempt, usage-required safety boundaries; 26 provider-free infrastructure/policy/calibration checks pass | B0 offline implementation record on 2026-08-09 |
| E-012 | Five original Agent fixtures have fixed hashes, no detected byte/row match against the ignored corpus, no `tests/` dependency, and public-outcome oracles; live collection is 8 cases in both modes and one explicit selector collects one cell | clean-room audit and offline collection on 2026-08-09 |
| E-013 | Agent report schema v5 has strict bounded loading, non-gating one-headless characterization, formal three-headless plus one-headed acceptance, exact comparison identity, and independent Judge calibration bound to settings and rubric hashes | report-policy and calibration checks on 2026-08-09 |

Detailed B0 investigation and conclusions are in [B0 research](b0-research.md).

## Private Evidence Policy

Ignored `evidence/private/` may contain local manifests, exact oracle values, labels, future windows, reference-output hashes, and evaluator artifacts. It must not be mounted into Agent-visible case roots or copied into tracked summaries.

The original corpus remains under ignored `business_data_mining_and_analysis_agent_special/`. No supplied Joblib file is loaded. Networked or archive-extraction scripts are not executed as part of offline qualification.

## Safe Promotion

Tracked evidence may record logical source IDs, hashes, schema/shape statistics, method, runtime identity, tolerance policy, limitations, and verdicts. It must not contain original business rows, exact private answers, source paths exposed to the Agent, transcripts, credentials, or unbounded logs.
