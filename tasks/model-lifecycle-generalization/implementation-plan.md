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
- Verified current train/evaluate/inference behavior with `pdm run pytest tests/test_ml_execution.py tests/test_agent_harness_first_slice.py -q`.

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
  - `regression.light_gbm`
  - `classification.xgboost`
  - `classification.light_gbm`
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

## Slice 6: Association Rule Models

### Scope

- Add model family:
  - `association_rules`
- Add model keys:
  - `association.apriori`
  - `association.mlxtend_apriori`
- Train from role bindings:
  - long format: `transaction_id`, `item`
  - wide basket format: `item_columns`
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

## Slice 7: Recommendation Models

### Scope

- Add model family:
  - `recommendation`
- Add model key:
  - `recommendation.item_similarity`
- Train from role bindings:
  - `user`
  - `item`
  - optional `rating`
- Persist reusable similarity artifact.
- Apply supports seed item, user id, or inline user history.

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

## Slice 8: Scenario-Centric Cleanup

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

- Whether Slice 8 should run before association/recommendation implementation to avoid carrying old UI assumptions into new model families.

## Accepted Decisions

- `data.feature.select` evolves directly into general role binding.
- Replace the table with `dataset_column_binding`; no runtime backward-compatible table alias is required.
- Database migration must cover both schema and data.
- Introduce `ModelFamily` and `ModelTaskKind`.
- `ModelCatalogEntry` role schemas and result contracts are in scope for this task packet.
- New Agent/service contracts should use `binding_id`, not `selection_id`.

## Review Findings

- The initial slice order was wrong because role-binding validation depends on catalog role schemas; catalog primitives now precede storage/tool role binding.
- Persisting both `role_bindings` and `feature_columns` / `target_columns` in the new table would create duplicate sources of truth; the new table now stores only canonical `role_bindings`.
- Carrying `selection_id` into the generalized contract would leak old feature-selection semantics; the new contract uses `binding_id`.
- New contracts should use `apply` rather than `inference`; this includes Agent tool naming, service request/result types, metadata fields, and stored task type values where applicable.
- Persisted `feature_columns` / `target_columns` metadata would create a second supervised-only contract; they should be removed and replaced by `train_role_bindings` / `apply_role_schema`.
- Scenario cleanup remains a sequencing risk. New association/recommendation work must not depend on scenario services or UI.
