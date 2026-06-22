# Changes Log

## Slice 1 - Expand Evaluation Metrics

### Task Packet Changes

- Created this log to track slice-organized changes.
- Recorded the first optimization target: expand classification and regression evaluation beyond a single primary metric.

### Source Changes

- None. Source mutation is waiting for explicit user start.

### Verification

- Not run. No source behavior has changed.

### Exploration Changes

- Recorded current implementation constraints:
  - `CandidateMetrics.metrics` and trained-model metadata metrics are scalar-only.
  - `evaluation.py` owns metric policy and metric snapshot construction.
  - Probability-dependent classification metrics need estimator probability/score access, not only labels.

### Pending Source Changes

- Awaiting explicit user start before source mutation.

### Slice Scope Update

- Expanded the candidate scope beyond ML Service to include Agent tool projection where evaluation evidence becomes user-visible.
- No source changes yet.

### Implemented Source Changes

- `src/xenix/services/ml/contracts.py`
  - Added `CandidateMetrics.details` for structured, JSON-serializable evaluation evidence.
- `src/xenix/services/ml/evaluation.py`
  - Added regression metrics: `mse`, `mape`, `explained_variance`, `residual_mean`, `residual_std`.
  - Added classification metrics: `balanced_accuracy`, macro precision/recall/F1.
  - Added structured classification details: labels, confusion matrix, classification report, and probability metric availability metadata.
  - Added conditional probability metrics: `roc_auc`, `pr_auc`, `log_loss`.
- `src/xenix/services/ml/models/base.py`
  - Passed estimator `predict_proba` output and class labels into metric snapshot building when available.
- `src/xenix/services/trained_model_metadata.py`
  - Added `evaluation_details` while keeping `evaluation_metrics` scalar-only.
  - Bumped trained model metadata default schema version to `3`.
- `src/xenix/services/agent/tools.py`
  - Added primary evaluation metric to completed training markdown.
  - Added metric summaries and probability-unavailable reasons to `model.task.query` markdown for evaluation tasks.
- Tests updated:
  - `tests/test_ml_registry.py`
  - `tests/test_ml_execution.py`
  - `tests/test_agent_harness_first_slice.py`

### Verification Results

- Passed: `pdm run pytest tests/test_ml_registry.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_task_query_summarizes_completed_evaluation`
- Passed: `pdm run pytest tests/test_ml_execution.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py`
- Passed: `pdm run pytest tests/test_agent_harness_foundation.py::test_chatbot_event_projection_omits_task_query_detail_action`
- Passed: `pdm run check`

### Working Tree Note

- Existing unrelated task workspace changes were present under `tasks/diagnose-missing-target-column/`; this slice did not touch them.

## Slice 2 - Fix Apply / Inference Naming Drift

### Task Packet Changes

- Recorded user claim and current exploration findings.
- No source changes yet; implementation is waiting for explicit start after Impact Handshake.
- Recorded user decision that no legacy alias is needed for `inference_model` or `run_inference_task`.

### Verification

- Not run for this slice yet.

### Scope Update

- User proposed expanding column role binding semantics to support semi-supervised learning in this slice.
- Recorded a revised candidate contract:
  - ordinary supervised models keep `feature + target`;
  - semi-supervised classifiers use `feature + partial_target`;
  - missing/blank `partial_target` values represent unlabeled rows for the initial implementation;
  - evaluation should use held-out labeled rows only.
- No source changes yet; implementation is waiting for explicit start after contract confirmation.

### Implemented Source Changes

- `src/xenix/services/ml/models/base.py`
  - Added `EncodedSemiSupervisedClassifier`.
  - Added `SemiSupervisedClassificationModelService`.
  - Added split logic where only labeled rows are held out for evaluation and unlabeled rows stay in the training side.
  - Added blank/null detection for unlabeled `partial_target` values.
- `src/xenix/services/ml/models/classification.py`
  - Added `classification.label_propagation`.
  - Added `classification.label_spreading`.
  - Added `classification.self_training`.
  - Added shallow parameter schemas for the three semi-supervised models.
- `src/xenix/services/ml/models/__init__.py`
  - Exported the new semi-supervised classification services.
- `src/xenix/services/ml/registry.py`
  - Registered the new semi-supervised models in the canonical catalog.
- `src/xenix/services/ml_service.py`
  - Changed complete-target validation to apply only to models that explicitly declare a `target` role.
  - Extended feature/label overlap validation to cover `partial_target`.
- `docs/30-unit-tdd/agent-harness.md`
  - Documented the Agent-facing `partial_target` contract.
- Tests updated:
  - `tests/test_ml_registry.py`
  - `tests/test_ml_execution.py`

### Verification Results

- Passed: `pdm run pytest tests/test_ml_registry.py`
- Passed: `pdm run pytest tests/test_ml_execution.py::test_semisupervised_classifier_uses_partial_target_and_labeled_holdout`
- Passed: `pdm run pytest tests/test_ml_execution.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums`
- Passed: `pdm run check`
- Passed: semi-supervised catalog/pipeline smoke with `PYTHONPATH=src`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py`

### Implemented Ordinary Supervised Model Additions

- `src/xenix/services/ml/models/classification.py`
  - Added Extra Trees, Histogram Gradient Boosting, SVC, calibrated LinearSVC, MLP, and MultinomialNB classification services.
  - Added shallow params and tuning-grid schemas for each new classifier.
  - Added non-negative preprocessing for MultinomialNB.
  - Added MLP hidden-layer schema projection to sklearn tuple params.
- `src/xenix/services/ml/models/regression.py`
  - Added ElasticNet, SVR, MLP, and Histogram Gradient Boosting regression services.
  - Added shallow params and tuning-grid schemas for each new regressor.
  - Added MLP hidden-layer schema projection to sklearn tuple params.
- `src/xenix/services/ml/models/__init__.py`
  - Exported the new ordinary supervised services.
- `src/xenix/services/ml/registry.py`
  - Registered the new ordinary supervised services.
- `tests/test_ml_registry.py`
  - Updated catalog count to 41.
  - Added schema assertions and direct fit/predict smoke coverage for the new ordinary supervised services.

### Ordinary Supervised Verification Results

- Passed: `pdm run pytest tests/test_ml_registry.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py`
- Passed: `pdm run pytest tests/test_ml_execution.py`
- Passed: `pdm run check`

### Implemented Source Changes

- `src/xenix/services/ml/contracts.py`
  - Renamed apply task contracts from `Inference*` to `Apply*`.
  - Renamed request payload field from `inference_model` to `apply_model`.
- `src/xenix/services/ml/types.py`
  - Renamed model adapter abstract method from `infer(...)` to `apply(...)`.
- `src/xenix/services/ml/models/base.py`
  - Renamed supervised apply implementation and internal variables/messages from inference to apply.
- `src/xenix/services/ml/models/association.py`
  - Renamed association apply implementation to `apply(...)` and switched to `request.apply_model`.
- `src/xenix/services/ml/models/recommendation.py`
  - Renamed recommendation apply implementation to `apply(...)` and switched to `request.apply_model`.
- `src/xenix/services/ml/operations/__init__.py`
  - Renamed worker entrypoint from `run_inference_task` to `run_apply_task`.
  - Updated worker logs and failure payload access to apply terminology.
- `src/xenix/services/ml_task_service.py`
  - Mapped `MLTaskType.APPLY` to `run_apply_task`.
  - Finalized apply tasks through `ApplyTaskResult`.
- `src/xenix/services/ml/remote_worker.py`
  - Registered only `run_apply_task`; no legacy `run_inference_task` alias.
- `src/xenix/services/ml/execution.py`
  - Updated SSH entrypoint allowlist to `run_apply_task`.
- `src/xenix/services/ml_service.py`
  - Constructed `ApplyTaskRequest` / `ApplyModelPayload`.
  - Built `ApplyInputFile` lists and manual apply CSV paths.
- `src/xenix/services/dataset_service.py`
  - Renamed manual inline CSV materialization to apply terminology and temp path `manual-apply`.
- `src/xenix/services/agent/tools.py`
  - Updated task request summary and model-key extraction for `apply_model`.
- `src/xenix/ui/tool_call_detail_view.py`
  - Updated detail projection lookup to `apply_model`.
- `src/xenix/ui/widgets/inference_row_editor.py`
  - Renamed to `src/xenix/ui/widgets/apply_row_editor.py`.
  - Renamed widget class to `ApplyRowEditorWidget`.
- Translation contexts for the renamed row editor were updated.
- Tests updated:
  - `tests/test_ml_execution.py`
  - `tests/test_ml_workers.py`
  - `tests/test_services.py`

### Addendum Source Changes

- `src/xenix/services/agent/tools.py`
  - Resolved `model.apply.input_files` entries before calling `MLService.apply`.
  - Added support for `artifact://...` apply inputs through `ArtifactService.resolve_uri`.
  - Added support for dataset id apply inputs through `DatasetService.get_dataset`.
  - Preserved absolute/path-like file inputs.
- `tests/test_agent_harness_first_slice.py`
  - Added coverage for `model.apply` using an artifact URI and a dataset id as `input_files`.

### Pending Naming Follow-up

- User flagged `input_files` as misleading after artifact URI and dataset id support.
- Proposed next change is to rename Agent-facing `model.apply.input_files` to `input_sources` while keeping worker-facing resolved `ApplyTaskRequest.input_files`.
- User also decided raw local path strings must be rejected at the Agent-facing boundary for privacy.

### Implemented Apply Source Boundary Changes

- `src/xenix/services/agent/tools.py`
  - Renamed provider-facing `model.apply.input_files` schema to `input_sources`.
  - Rejected raw local path strings at the Agent-facing boundary.
  - Kept `artifact://...` and registered dataset id resolution.
- `src/xenix/services/agent/dev_fixtures.py`
  - Replaced mock raw apply path with an artifact URI.
- `docs/30-unit-tdd/agent-harness.md`
  - Updated `model.apply` contract to use `input_sources` and document that raw filesystem paths are not accepted.
- `tests/test_agent_harness_first_slice.py`
  - Updated provider calls to use `input_sources`.
  - Added a privacy-boundary assertion that raw paths are rejected.

### Residual Inference Terms

- `src/xenix/services/dataset_inspection.py::infer_column_kind` remains intentionally; it means type inference, not model inference.
- Storage migrations, storage migration tests, durable docs, vanished translations, and OpenInference terms remain intentionally historical/external.

### Verification Results

- Passed: `pdm run pytest tests/test_ml_execution.py`
- Passed: `pdm run pytest tests/test_ml_workers.py`
- Passed: `pdm run pytest tests/test_services.py::test_dataset_service_materializes_manual_apply_csv_and_exports_utf8_by_default`
- Passed: `pdm run pytest tests/test_services.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_model_apply_accepts_artifact_uri_or_dataset_id_input_file`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums tests/test_agent_harness_first_slice.py::test_agent_harness_model_apply_accepts_artifact_uri_or_dataset_id_input_file tests/test_agent_harness_first_slice.py::test_agent_harness_first_slice_runs_from_file_to_apply_result`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py`
- Passed: `pdm run pytest tests/test_storage_bootstrap.py::test_storage_bootstrap_migrates_v7_inference_values_to_apply`
- Passed: `pdm run check`

## Slice 3 - Expand Supervised Model Catalog

### Task Packet Changes

- Recorded proposed classification and regression model additions.
- Recorded exploration finding that current `ml/classification` and `ml/regression` teaching directories cover existing native model families, while the requested additions are catalog expansion rather than direct script migration.
- Recorded recommendation to include ordinary supervised estimators now and defer semi-supervised estimators until the service contract can represent partially labeled data.

### Source Changes

- None. Source mutation is waiting for explicit user start.

### Verification

- Not run for this slice yet.
