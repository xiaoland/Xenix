# P1.5 Model Usability Execution Task

## Objective & Hypothesis

- Objective: implement the `P1.5 Model Usability` slice defined in `p1-5-solidify.md`.
- Hypothesis: the expanded P0/P1 native model catalog becomes substantially more usable when users can see concise model guidance, curated scenario defaults, and explicit supervised result ranking.

## Scope Executed

- Added catalog usability metadata to `ModelCatalogEntry`:
  - `family`
  - `guidance`
  - `recommendation_tier`
- Added family/guidance/tier metadata for regression, classification, and clustering model services.
- Refreshed supervised scenario defaults:
  - regression defaults: `regression.linear`, `regression.bayesian_ridge`, `regression.gradient_boosting`
  - classification defaults: `classification.logistic_regression`, `classification.naive_bayes`, `classification.gradient_boosting`
- Improved model-selection UI:
  - recommended plan section
  - additional compatible models section
  - model family and recommendation label
  - concise guidance sentence per model card
  - ordering by selected default priority, recommendation tier, family, and display name
- Improved supervised training dashboard comparison:
  - result cards sort by primary metric once metrics are available
  - succeeded cards show rank text such as `Rank #1 by r2`
- Updated Simplified Chinese translations for P1.5 UI strings and regenerated translation outputs.

## Guardrails Touched

- Legacy `F:\CODING\Project\Xenix\ml` scripts stayed read-only.
- Storage schema stayed unchanged.
- ML task lifecycle, trained-model persistence, and best-model selection semantics stayed unchanged.
- Clustering profile output stayed out of this slice and remains tracked in `clustering-profile-v1-5-solidify.md`.
- Existing clustering `cluster_assignments.csv` open action stayed covered by UI tests.

## Verification

- Command:
  - `pdm run pytest tests/test_ml_registry.py tests/test_scenario_ui.py tests/test_scenario_workflow.py -q`
  - `pdm run i18n-extract`
  - `pdm run i18n-compile`
  - `pdm run pytest tests/test_ml_registry.py tests/test_scenario_ui.py tests/test_scenario_workflow.py tests/test_i18n.py -q`
  - `pdm run python -m compileall src tests scripts`
  - `pdm run pytest -q`
- Observed:
  - targeted registry/UI/workflow suite passed: `27 passed`
  - i18n-aware targeted suite passed: `29 passed`
  - compile succeeded
  - full pytest suite passed: `63 passed`
  - `zh_CN` translation compile reported `445 finished and 0 unfinished`

## Notes

- `xenix_en_US.ts` remains aligned with extracted source strings; unfinished entries continue to fall back to source English text.
- `git status` may warn about denied access to local pytest temporary directories during broad status scans.
