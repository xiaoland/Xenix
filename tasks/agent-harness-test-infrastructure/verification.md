# Agent Harness Benchmark Verification

This file owns objective proof and the run ledger. Scope remains
[packet.md](packet.md); ordered source work lives in
[implementation-slices.md](implementation-slices.md).

## Proof Matrix

| Boundary | Deterministic proof | Live proof |
| --- | --- | --- |
| shared composition | headless import, one builder call path, app compatibility, no Qt/storage lifecycle capture | Kimi cell exercises builder-created real graph |
| provider/model matrix | typed config parse, full model expansion, filter, sequential continuation, no provider injection | one result or explicit safe failure per configured model |
| title suppression | pre-titled Thread is not initial-title eligible and emits no title event/usage | cell transcript counters contain primary work only |
| metrics | canonical fixture snapshots cover message/Tool/status/usage/retry/missing-usage folds | result counters reconcile with public final projection |
| output location | case locator covers valid/latest reference, source/stale/malformed/unreadable/no reference | located Dataset matches the cell's final successful reference |
| cleaning oracle | small frames cover correct, retained report/header, duplicates, missing/corrupt rows | April terminal data checks and direct shape/content evidence agree |
| failure persistence | pass, outcome fail, invalid setup, runtime error, measurement error, and write failure | failing cells do not abort later matrix cells |
| privacy/isolation | serializer denylist probes plus temp-path assertions | source/config hashes unchanged; report inspection is bounded |
| AIMock removal | old config extra-field compatibility, settings/UI/provider/i18n regression, scoped search | real provider cells run with no development override |
| default stability | targeted tests, `pdm run check`, default `pdm run test` | live command remains explicit and outside default tests |

## Command Evidence Slots

Record exact commands, exit codes, and bounded findings here during execution:

| Stage | Command | Result | Evidence |
| --- | --- | --- | --- |
| composition + affected boundaries | `pdm run test tests/test_agent_composition.py tests/test_agent_harness_benchmark.py tests/test_agent_settings.py tests/test_llm_service_retry.py tests/test_agent_skill_catalog.py tests/test_agent_harness_cleaning_efficiency.py tests/test_main.py tests/test_settings_dialog.py` | PASS | 103 passed; composition is Qt-free at import and app/benchmark share it |
| benchmark offline | same focused command above | PASS | 10 benchmark-kernel/oracle tests passed without a provider call |
| AIMock/settings/UI | `pdm run i18n-extract`; `pdm run i18n-compile`; focused settings tests | PASS | product AIMock card/config/fixture removed; historical extra config key loads then drops on save |
| i18n/check | `pdm run check` | PASS | skill catalog check and compileall passed |
| Kimi reference cell | explicit `benchmark-agent-harness --model kimi/kimi-k2.6` | PASS, completed outcome fail | persisted bounded report; see live matrix below |
| remaining model cells | explicit one-model sequential `benchmark-agent-harness` commands | PASS, completed outcome fail | one persisted bounded report for every other configured model |
| default regression | `pdm run test` | PASS | 363 tests + 58 main-window tests passed; no real provider call |

## V1 Live Matrix (one run per configured model)

All cells used the pinned April workbook, a fresh temporary runtime, a
pre-titled Thread, and `provider=None` through the configured real
`LLMService`. `completed` means the canonical turn settled and the report was
persisted; it does not mean that the cleaning outcome passed.

| Model | Status | Outcome | Turn s | Total tokens | Rounds | Tool calls / failed results | Terminal shape | Failed outcome checks |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `kimi/kimi-k2.6` | completed | fail | 830.2 | 151,730 | 8 | 7 / 1 | 486120×50 | duplicates, expected shape, business rows |
| `bailian/qwen3.6-plus` | completed | fail | 1200.3 | 251,165 | 8 | 7 / 1 | 485790×50 | header promotion, business rows |
| `bailian/qwen-flash` | completed | fail | 30.5 | 12,470 | 2 | 1 / 0 | none | terminal output and dependent data checks |
| `deepseek/deepseek-v4-pro` | completed | fail | 695.3 | 191,535 | 14 | 14 / 1 | 486119×50 | header promotion, duplicates, expected shape, business rows |

Every cell passed `canonical_completion`, `source_unchanged`, and
`state_isolated`. The matrix therefore distinguishes model/task behavior from
benchmark infrastructure or source/configuration mutation. These are single
observations, not thresholds or statistical rankings. A bounded report scan
across all four JSON files found zero API-key, endpoint, source/configuration
path, prompt/data, canonical-id, Tool-payload, or workbook-name markers.

## Completion Checklist

| Claim | Proof |
| --- | --- |
| Production-equivalent boundary | shared builder used by app and benchmark |
| Real provider path | Harness `provider=None`, configured `LLMService` observed |
| Model matrix | every configured fq model gets one fresh sequential cell |
| Benchmark, not only test | persisted outcome + token/time/message/Tool/failure metrics |
| Meaningful oracle | header/report rows fixed, duplicates removed, business rows preserved |
| Failure visibility | outcome-failing run still writes metrics/result |
| State/privacy isolation | temp-home writes only; bounded secret-free JSON |
| Default stability | ordinary test command remains offline and deterministic |
| AIMock replacement avoided | AIMock absent; no replay/provider double added |
| Metric honesty | missing usage is null; sampling/retry/usage counts stay distinct |
| Timing honesty | attachment-inclusive turn and oracle time separated; title task absent |

No second case, repeated trials, aggregate statistics, hosted storage, generic
scorer framework, or automated performance threshold is required for V1.

## Run Ledger (Newest First)

| Date | Scope | Result | Evidence / follow-up |
| --- | --- | --- | --- |
| 2026-07-20 | V1 implementation, real-provider matrix, and full regression | PASS | Four configured models completed and persisted reports; all outcome failures are recorded above rather than hidden. Follow up in a separate performance slice; do not overfit V1 to any one model. |
| 2026-07-20 | AIMock removal | PASS | Removed service/settings/UI/config/fixture surface; legacy extra key compatibility and UI/i18n regressions passed. |
| 2026-07-20 | Offline benchmark infrastructure | PASS | Shared headless composition, frozen external settings source, matrix kernel, terminal locator, oracle, privacy serializer, and focused tests completed. |
| 2026-07-20 | Implementation preflight | PASS | Production graph, settings, worker, fixture, terminal selection, metrics, privacy, status and cleanup branches rehearsed |
| 2026-07-20 | Benchmark reframing | PASS | Resource counts become benchmark outputs; cleaning assertions become outcome oracle |
| 2026-07-20 | Black-box oracle correction | SUPERSEDED | Historical modeling gate replaced by first outcome-bearing cleaning benchmark |
| 2026-07-20 | Small-first rescope | PASS | V1 remains one shared composition, one runner, one case, and AIMock removal |
| 2026-07-19 | Benchmark research and poly-file split | PASS | Outcome-first and isolated-run lessons retained; platform abstractions deferred |

The first V1 baseline is complete. A second case, repetitions, thresholds, and
model-specific remediation remain deliberately out of scope.
