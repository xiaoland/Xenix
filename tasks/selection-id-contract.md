# Selection ID Contract

## Objective & Hypothesis

Make feature/target column selection an immutable persisted snapshot referenced by `selection_id`, so Agent training and tuning tools do not have to repeat dataset and column arguments.

## Guardrails Touched

- Storage schema changes must increment SQLite `user_version` and include a forward migration.
- Dataset inspection remains owned by `DatasetService`.
- ML task request payloads remain self-contained by storing expanded dataset and column selection data.
- Inference uses trained model metadata as the feature contract.

## Verification

- Add fresh bootstrap and migration coverage for the column selection table.
- Update ML execution tests to create selections before training/tuning.
- Update Agent first-slice tests to call `data.feature.select`, train by `selection_id`, and infer by `trained_model_id`.
- `pdm run pytest` passes: 91 tests.
- Enhanced column-selection validation reports missing columns, closest available suggestions, and exact available column names; `pdm run pytest` passes: 93 tests.
