## Objective & Hypothesis

- Objective: replace the unstable Vega word-cloud path with a dedicated `analysis.graph.wordcloud_spec` contract, then align skill guidance, runtime validation, error response, and durable docs around that contract.
- Hypothesis: word clouds become materially more reliable once Xenix owns a compact word-cloud mode instead of asking the Agent to synthesize a fragile Vega word-cloud spec.

## Guardrails Touched

- `AGENTS.md` root operating model and impact handshake
- `docs/00-meta/mode-a-explore.md`
- `docs/00-meta/implementation-taste.md`
- `src/xenix/services/AGENTS.md`

## Verification

- `pdm run pytest tests/test_analysis_graph.py -q` -> 17 passed
- `pdm run pytest tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py -q` -> 31 passed
- `pdm run pytest tests/test_analysis_graph.py tests/test_agent_harness_foundation.py tests/test_agent_harness_first_slice.py -q` -> 48 passed
- `pdm run check` -> passed

## Current Understanding

- `analysis.graph` now exposes mutually exclusive modes: ordinary Vega `spec` or dedicated `wordcloud_spec`.
- The word-cloud mode is Xenix-owned rather than raw-library-shaped:
  - upstream still must use `data.query` or `data.transform` to prepare chart-ready rows, usually `word` and `count`;
  - Chinese text must already be segmented upstream;
  - the mode defaults to Top 80, enforces a minimum of Top 20, prefers mostly horizontal placement, applies bounded font-size defaults, and always emits tooltip text.
- Runtime behavior now matches the new contract:
  - Vega word-cloud transforms are rejected with a directed repair message to use `wordcloud_spec`;
  - dedicated word-cloud failures return structured retry metadata (`error_code`, `error_details`, `repair_hints`, `retryable`);
  - tolerance is relaxed so dense clouds do not fail purely because a minority of terms cannot be placed.
- The Agent-facing guidance is simplified:
  - word-cloud-specific instructions were removed from the generic Vega reference;
  - the obsolete Vega word-cloud template asset was deleted;
  - durable docs now describe the new `wordcloud_spec` contract and stop advertising Vega word clouds.
- Packaging and smoke coverage were updated:
  - `wordcloud` was added as a dependency;
  - app smoke coverage now exercises the dedicated `wordcloud_spec` path.
- Commit remains intentionally unperformed because the user required explicit instruction before any future commit.

## Next Step

- Wait for user review or follow-up adjustments. Commit only if the user gives an explicit commit instruction.
