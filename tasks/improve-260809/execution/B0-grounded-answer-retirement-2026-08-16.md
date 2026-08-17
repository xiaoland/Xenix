# B0-GR Legacy Grounded-Answer Check Retirement — 2026-08-16

## Outcome

Retired the free-prose `_grounded_final_answer` regex from the five sibling B0
legacy cases (clustering, forecasting, recommendation, text-insight, and
rainy-season-restock), leaving each case's deterministic semantic layer
structural (exact Dataset + linked Artifact + integrity). Added a benchmark
tripwire against reintroducing free-prose grounding. The cleaning case was
retired earlier by `IH-O4-E3`; the five Judge-based cohort cases already used
structural markers plus the Judge and were untouched.

## Implemented State Diff

- `test_ml_clustering.py`: removed `_grounded_final_answer` +
  `_profile_clause` + `import unicodedata` (-48 lines).
- `test_ml_forecasting.py`: removed `_grounded_final_answer` +
  `import unicodedata` (-26 lines).
- `test_ml_recommendation.py`: removed `_grounded_final_answer` +
  `import unicodedata` (-31 lines).
- `test_ml_text_insight.py`: removed `_grounded_final_answer` +
  `import unicodedata` (-23 lines).
- `test_rainy_season_restock.py`: removed `_grounded_final_answer_observed`
  plus its six helpers (`_normalized_answer_text`, `_rainwear_scope_observed`,
  `_three_week_target_observed`, `_inventory_rule_observed`,
  `_floor_at_zero_observed`, `_sku_quantity_pair_observed`) and
  `import re`/`import unicodedata` (-145 lines).
- `benchmarks/agent_harness/AGENTS.md`: added the deterministic-structural
  tripwire.

Each case's `semantic_checks` is now `(exact_*_dataset, public_artifact_linked,
...)` or the equivalent structural set; no case's remaining checks are empty.

## Verification

- `pdm run test -q`: 146 passed.
- `pdm run check`: passed.
- `pdm run benchmark-agent-harness-check -q`: 33 passed.
- Headless and headed `--collect-only`: 13 live cases each.

## Judge Decision (Sir, 2026-08-16)

Sir selected the Judge model: same kimi provider/key as the subject, model
`kimi-2.7` (subject is `kimi/kimi-k2.6`), so the Judge is subject-disjoint.
The untracked snapshot is `.runtime/dev/config/judge_settings.json`
(`default_fq_model_key: kimi/kimi-2.7`). It loads via
`load_settings_snapshot` (sha256 `43E55124AE39C6CD...`). The five exact-rubric
calibrations are still pending: they require live Judge calls against
`ml_formal_judge_calibrations.json`.

## Acceptance

The legacy free-prose grounding class is eliminated; the deterministic layer is
structural across the B0 cases, and the Judge path for explanation quality is
configured and ready. No paid re-run is required for this retirement.
