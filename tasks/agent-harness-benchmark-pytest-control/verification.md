# Verification Ledger

| Scope | Command | Result | Notes |
| --- | --- | --- | --- |
| Dynamic generic infra | `pdm run test tests/test_agent_harness_benchmark_infra.py` | PASS | 17 offline tests; no provider call. |
| Benchmark discovery | `pdm run benchmark-agent-harness -- --collect-only -q` | PASS | Two case modules collected with no provider access. |
| Live option routing | selected graph case with nonexistent `--llm-settings` and temporary `--output-dir` | PASS | No provider call; one persisted `invalid_setup/missing_llm_settings` result and expected pytest exit 1. |
| Live Kimi graph cell | `pdm run benchmark-agent-harness -- -k test_revenue_by_region_chart ...` | PASS | `kimi/kimi-k2.6`: completed, semantic pass, integrity true, judge completed, 16,171 subject tokens, 22.802 s; 2,725-byte persisted report contained no checked raw artifact/path/config markers. |
| Full regression | `pdm run test` | PASS | 371 non-UI + 58 UI tests passed; only existing sklearn warnings. Default collection remained `tests/` only. |
