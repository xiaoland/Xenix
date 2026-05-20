# Implementation Plan

## Objective

Implement the generalized model lifecycle in slices that avoid strengthening the old scenario-first path.

## Slice 0: Durable Contract Solidification

### Scope

- Promote `model = reusable analyzer` to PRD.
- Update ML task lifecycle docs with generalized role binding and artifact result contracts.
- Document the accepted replacement of `DatasetColumnSelectionRow` with `DatasetColumnBindingRow`.
- Decide exact enum placement for `ModelFamily` and `ModelTaskKind`.
- Document the accepted terminology shift from inference to apply.

### Files Likely Touched

- `docs/10-prd/product-scope.md`
- `docs/20-product-tdd/ml-task-lifecycle.md`
- docs or tests that mention `model.inference` as the forward-looking contract
- `tasks/model-lifecycle-generalization/data-model-design.md`
- `tasks/model-lifecycle-generalization/implementation-plan.md`

### Verification

- Documentation review against task packet.
- No production test run required unless docs lint is later introduced.

### Status

- Completed on 2026-05-20.
- Updated PRD/Product TDD durable docs to define model as reusable analyzer, role binding as the training input contract, `model.apply` as the forward apply contract, and artifact descriptors as the output contract.
- No production code changes were made in this slice.

## Slice 1: Catalog Primitives And Role Schemas

### Scope

- Add `ModelFamily` and `ModelTaskKind`.
- Extend `ModelCatalogEntry` with train role schemas, apply role schemas, and result contract metadata.
- Add default role schemas for existing supervised, clustering, and anomaly services.
- Keep existing model keys and training behavior unchanged.

### Files Likely Touched

- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/models/base.py`
- `src/xenix/services/ml/models/*.py`
- `src/xenix/services/agent/tools.py`
- `tests/test_ml_registry.py`
- `tests/test_agent_harness_first_slice.py`

### Verification

- `pdm run pytest tests/test_ml_registry.py tests/test_agent_harness_first_slice.py -q`

### Status

- Completed on 2026-05-20.
- Added `ModelFamily`, `ModelTaskKind`, role-schema DTOs, and result-contract metadata to model catalog entries.
- Existing model services derive default supervised, clustering, and anomaly role schemas from current `ProblemKind` and `requires_target`.
- `model.metadata` now exposes family/task/schema/result metadata and supports family/task filters.
- Verified with `pdm run pytest tests/test_ml_registry.py tests/test_agent_harness_first_slice.py -q`.

## Slice 2: Role Binding Storage And Tool Contract

### Scope

- Evolve `data.feature.select` into general role binding.
- Require canonical `role_bindings`.
- Return `binding_id` and generalized `role_bindings`.
- Add role schema validation using model catalog metadata when `model_key` is provided.
- Replace `DatasetColumnSelectionRow` and repository naming with `DatasetColumnBindingRow`.
- Add schema migration and data migration from `dataset_column_selection` to `dataset_column_binding`.

### Files Likely Touched

- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/migrations.py`
- `src/xenix/services/storage/repositories/column_selections.py` or renamed repository module
- `src/xenix/services/agent/tools.py`
- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml_service.py`
- `tests/test_agent_harness_first_slice.py`
- `tests/test_migrations.py`
- new focused tests if needed

### Verification

- `pdm run pytest tests/test_agent_harness_first_slice.py tests/test_repositories.py -q`
- migration test proving old selection rows become binding rows
- Existing supervised first-slice train/apply behavior must keep passing after test and contract naming is updated.

### Status

- Completed on 2026-05-20.
- Replaced `dataset_column_selection` fresh schema with `dataset_column_binding`.
- Added v6 -> v7 schema/data migration that converts old feature/target selection rows into canonical role bindings and drops the old table.
- Updated `data.feature.select`, `model.train`, and `model.hyper_train` to use `role_bindings` / `binding_id` at the Agent and service boundary.
- Kept the existing execution-layer `ColumnSelection` projection inside `MLService` so current model adapters continue to run until Slice 3 generalizes task requests.
- Verified with `pdm run pytest tests/test_storage_bootstrap.py tests/test_repositories.py tests/test_agent_harness_first_slice.py tests/test_ml_execution.py -q`.

## Slice 3: Lifecycle Request Generalization

### Scope

- Replace training request `column_selection` with generalized role binding.
- Extend trained model metadata with family/task kind, `train_role_bindings`, and `apply_role_schema`.
- Remove persisted `feature_columns` and `target_columns` metadata fields; derive supervised display labels on demand from role bindings.
- Keep existing supervised, clustering, and anomaly services compatible.

Clarification:

- This task includes the `ModelCatalogEntry` changes.
- The earlier phrase "后续会暴露" means "in a later slice of this same task packet", not "out of scope".

### Files Likely Touched

- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/trained_model_metadata.py`
- `src/xenix/services/ml/models/base.py`
- `src/xenix/services/ml/models/*.py`
- `tests/test_ml_registry.py`
- `tests/test_ml_execution.py`

### Verification

- `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py -q`

### Status

- Completed on 2026-05-20.
- Replaced persisted fit/tuning/evaluate request `column_selection` payloads with `train_role_bindings`.
- Kept `ColumnSelection` as a runtime projection property for existing model adapters only.
- Updated trained-model metadata to schema v2 with `model_family`, `model_task_kind`, `train_role_bindings`, `apply_role_schema`, and `result_contract`.
- Removed persisted trained-model metadata `feature_columns` and `target_columns`.
- Verified current train/evaluate/apply behavior with `pdm run pytest tests/test_ml_execution.py tests/test_agent_harness_first_slice.py -q`.

## Slice 4: Generalized Apply Contract And Result Artifacts

### Scope

- Replace the legacy/current Agent/service contract name `model.inference` with `model.apply`.
- Rename or migrate stored task type values from `inference` to `apply` where they are persisted.
- Change apply/service result handling from one prediction CSV path to artifact descriptors.
- Preserve current `output_file_path` compatibility for supervised prediction tests.
- Support preview kinds:
  - table
  - text
  - markdown
  - image
  - file
  - model
- Ensure Agent tool result payloads include artifact links and summaries.

### Files Likely Touched

- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/ml/models/base.py`
- `src/xenix/services/ml_service.py`
- `src/xenix/services/artifact_service.py`
- `src/xenix/services/agent/tools.py`
- `tests/test_agent_harness_first_slice.py`
- `tests/test_ml_execution.py`

### Verification

- `pdm run pytest tests/test_ml_execution.py tests/test_agent_harness_first_slice.py -q`

### Status

- Partially completed on 2026-05-20.
- Replaced the Agent-facing tool contract `model.inference` with `model.apply`.
- Replaced persisted `MLTaskType.INFERENCE` / `inference` values with `MLTaskType.APPLY` / `apply`.
- Replaced persisted ML task artifact kind `inference_result` with `apply_result`.
- Added v7 -> v8 data migration for old task and artifact values.
- Renamed the service-facing first-slice entrypoint from `MLService.infer(...)` to `MLService.apply(...)`.
- The low-level worker operation and current sklearn adapter method names still use `inference` / `infer` internally; they are implementation details and should be renamed when the lower adapter contract is generalized.
- Generalized multi-artifact result descriptors are still pending beyond the current CSV apply-result artifact metadata.

## Slice 5: Dependency-Heavy Supervised Models

### Scope

- Add accepted dependencies:
  - `xgboost`
  - `lightgbm`
- Add supervised model services:
  - `regression.xgboost`
  - `regression.lightgbm`
  - `classification.xgboost`
  - `classification.lightgbm`
- Keep them inside the supervised compatibility path.

### Files Likely Touched

- `pyproject.toml`
- `pdm.lock`
- `src/xenix/services/ml/models/regression.py`
- `src/xenix/services/ml/models/classification.py`
- `src/xenix/services/ml/registry.py`
- `tests/test_ml_registry.py`
- `tests/test_ml_execution.py`
- packaging smoke tests if dependency behavior requires it

### Verification

- `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py -q`
- `pdm run python -m compileall src tests scripts`

### Status

- Completed on 2026-05-20.
- Added `xgboost` and `lightgbm` to runtime dependencies.
- Added XGBoost and LightGBM regression/classification services to the native registry.
- Added a label-encoding wrapper for XGBoost classification so business labels such as `stay` / `leave` remain valid external labels.
- Verified through catalog tests and targeted ML execution regression tests.

## Slice 6: Association Rule Models

### Scope

- Add model family:
  - `association_rules`
- Add model keys:
  - `association.apriori_apyori`
  - `association.apriori_mlxtend`
- Train from role bindings:
  - wide basket format: `item`
- Persist reusable rule artifact.
- Apply uses rule artifacts with basket input and produces recommendations with support/confidence/lift.

### Files Likely Touched

- `src/xenix/services/ml/models/association.py`
- `src/xenix/services/ml/models/base.py` or new analyzer base
- `src/xenix/services/ml/registry.py`
- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/agent/tools.py`
- `tests/test_ml_registry.py`
- `tests/test_ml_execution.py`
- `tests/test_agent_harness_first_slice.py`

### Verification

- Association train writes rules artifact.
- Association apply writes recommendation artifact.
- Agent tool result returns artifact links.

### Status

- Completed for wide basket input on 2026-05-20.
- Added both legacy algorithm backends as model services:
  - `association.apriori_apyori`
  - `association.apriori_mlxtend`
- Both train through `model.train` from `item` role bindings and apply through `model.apply` using persisted rules.
- Long transaction-table input remains a future extension; it is not silently supported.

## Slice 7: Recommendation Models

### Scope

- Add model family:
  - `recommendation`
- Add model key:
  - `recommendation.item_similarity`
- Train from role bindings:
  - `user`
  - `item`
  - `rating`
- Persist reusable similarity artifact.
- Apply supports seed item files or inline seed item rows through the trained `item` role.

### Files Likely Touched

- `src/xenix/services/ml/models/recommendation.py`
- `src/xenix/services/ml/registry.py`
- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/agent/tools.py`
- `tests/test_ml_registry.py`
- `tests/test_ml_execution.py`
- `tests/test_agent_harness_first_slice.py`

### Verification

- Recommendation train writes similarity artifact.
- Recommendation apply writes top-N recommendation artifact.
- Agent tool result returns artifact links.

### Status

- Completed for item-to-item similarity on 2026-05-20.
- Added `recommendation.item_similarity`.
- Training uses `user`, `item`, and `rating` role bindings.
- Apply accepts the trained item column and writes top-N recommendation rows.
- User-history apply remains a future extension; it is not silently supported.

## Slice 8: EvaluationKind Extraction

### Objective

Prevent `ProblemKind` from becoming the catch-all enum for every future model family. Move evaluation policy semantics to `EvaluationKind` while keeping `ModelFamily` and `ModelTaskKind` as the product and apply-behavior axes.

### Scope

- Add `EvaluationKind`.
- Add `evaluation_kind` to `ModelCatalogEntry`.
- Add `evaluation_kind` to trained-model metadata.
- Replace `get_default_policy(problem_kind)` with an API based on `EvaluationKind` plus task-specific summary metric metadata.
- Remove the transitional `ProblemKind.ANALYSIS` value added during association/recommendation integration.
- Make `TrainedModelRow.problem_kind` nullable legacy metadata, or otherwise stop requiring it for new non-legacy analyzers.
- Preserve regression/classification metrics and stratified split behavior.
- Preserve clustering/anomaly/association/recommendation training and apply behavior.
- Keep `ProblemKind` only where existing storage compatibility requires it.

### Proposed EvaluationKind Values

- `regression`: regression metric policy (`r2`, `rmse`, `mae`) and regression CV scoring.
- `classification`: classification metric policy (`f1_weighted`, `accuracy`, precision/recall) and stratified split.
- `summary`: no holdout evaluation; task-specific primary summary metric such as `cluster_count`, `anomaly_count`, `rule_count`, or `recommendation_count`.
- `none`: no evaluation policy and no automatic follow-up evaluation.

### Data Model Direction

- `EvaluationPolicySnapshot` should carry `evaluation_kind`, not `problem_kind`.
- `TaskRequestBase` / `TaskResultBase` should stop requiring `problem_kind`.
- `TrainedModelMetadata` should persist `evaluation_kind`.
- `TrainedModelRow.problem_kind` becomes nullable legacy compatibility data.
- A schema migration is required if the SQLite `trained_model.problem_kind` column is currently `NOT NULL`.

### Files Likely Touched

- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/evaluation.py`
- `src/xenix/services/ml/contracts.py`
- `src/xenix/services/ml/models/*.py`
- `src/xenix/services/ml_service.py`
- `src/xenix/services/ml_task_service.py`
- `src/xenix/services/trained_model_metadata.py`
- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/migrations.py`
- `src/xenix/services/agent/tools.py`
- `tests/test_ml_registry.py`
- `tests/test_ml_execution.py`
- `tests/test_storage_bootstrap.py`
- `tests/test_repositories.py`
- `tests/test_agent_harness_first_slice.py`

### Implementation Plan

1. Add `EvaluationKind` and expose it through model catalog metadata.
2. Assign evaluation kinds in model services:
   - regression services -> `regression`
   - classification services -> `classification`
   - clustering/anomaly/association/recommendation services -> `summary`
3. Add task-specific summary metric metadata to catalog defaults or service class attributes.
4. Change evaluation policy creation to use catalog evaluation metadata instead of `ProblemKind`.
5. Replace task request/result `problem_kind` payloads with `evaluation_kind`.
6. Persist `evaluation_kind` in trained-model metadata.
7. Add storage migration to relax or deprecate `trained_model.problem_kind`.
8. Remove `ProblemKind.ANALYSIS` and update association/recommendation services.
9. Update Agent `model.metadata` to expose/filter by `evaluation_kind`; keep or deprecate `problem_kind` filter only if required by existing tests.
10. Update tests and run full regression.

### Verification

- `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py tests/test_storage_bootstrap.py tests/test_repositories.py tests/test_agent_harness_first_slice.py -q`
- `pdm run pytest -q`
- Residual scan confirms no `ProblemKind.ANALYSIS` remains in `src` or tests.

### Status

- Completed on 2026-05-20.
- Added `EvaluationKind` to catalog, evaluation policy snapshots, task requests/results, Agent metadata, and trained-model metadata.
- Removed `ProblemKind.ANALYSIS`; association and recommendation catalog entries now expose `problem_kind = null`, `evaluation_kind = summary`, and task-specific summary metric names.
- Added v8 -> v9 schema/data migration:
  - `trained_model.problem_kind` becomes nullable.
  - persisted `analysis` problem-kind rows migrate to `NULL`.
  - trained-model metadata receives `evaluation_kind`.
  - old ML task request/result payloads move `problem_kind` into `evaluation_kind` and policy snapshots.
- Verified targeted registry, storage bootstrap, repository, ML execution, and Agent harness tests; full `pdm run pytest -q` passed with 109 tests.

## Slice 9: Scenario-Centric Cleanup

### Scope

- Remove, quarantine, or stop routing through scenario-first UI/services where they conflict with Chatbot-first product truth.
- Migrate useful defaults or copy into Agent/service contracts if still needed.
- Update tests to stop treating scenario home as the acceptance path for new capabilities.

### Files Likely Touched

- `src/xenix/ui/*scenario*`
- `src/xenix/services/*scenario*`
- `tests/test_scenario_ui.py`
- `tests/test_scenario_workflow.py`
- docs and translations

### Verification

- Chatbot/Agent workflow tests remain green.
- Removed scenario paths do not break app startup.

## Open Sequencing Question

- Whether Scenario-Centric Cleanup should run immediately after EvaluationKind extraction or after the lower-level internal `inference` naming cleanup.

## Accepted Decisions

- `data.feature.select` evolves directly into general role binding.
- Replace the table with `dataset_column_binding`; no runtime backward-compatible table alias is required.
- Database migration must cover both schema and data.
- Introduce `ModelFamily` and `ModelTaskKind`.
- Introduce `EvaluationKind` so `ProblemKind` does not expand with future model families.
- `ModelCatalogEntry` role schemas and result contracts are in scope for this task packet.
- New Agent/service contracts should use `binding_id`, not `selection_id`.

## Review Findings

- The initial slice order was wrong because role-binding validation depends on catalog role schemas; catalog primitives now precede storage/tool role binding.
- Persisting both `role_bindings` and `feature_columns` / `target_columns` in the new table would create duplicate sources of truth; the new table now stores only canonical `role_bindings`.
- Carrying `selection_id` into the generalized contract would leak old feature-selection semantics; the new contract uses `binding_id`.
- New contracts should use `apply` rather than `inference`; this includes Agent tool naming, service request/result types, metadata fields, and stored task type values where applicable.
- Persisted `feature_columns` / `target_columns` metadata would create a second supervised-only contract; they should be removed and replaced by `train_role_bindings` / `apply_role_schema`.
- `ProblemKind.ANALYSIS` was removed by Slice 8; future analyzer additions must use `EvaluationKind`, `ModelFamily`, and `ModelTaskKind` rather than expanding `ProblemKind`.
- Scenario cleanup remains a sequencing risk. New association/recommendation work must not depend on scenario services or UI.
