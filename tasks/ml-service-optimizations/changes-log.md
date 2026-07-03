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

### Implemented Source Changes

- `src/xenix/services/ml/contracts.py`
  - Added optional `final_model_artifact_path` to fit and tuning task results.
- `src/xenix/services/ml/models/base.py`
  - Ordinary supervised `fit()` and `tune()` now write both an evaluation model and a final apply model.
  - Semi-supervised `fit()` now writes both an evaluation model and a final apply model.
  - Key-driver reports are generated from the final apply model.
- `src/xenix/services/ml_task_service.py`
  - Copies `final_model_artifact_path` into the canonical trained-model artifact path when available.
  - Preserves `evaluation_model_artifact_path` in result payload for follow-up evaluation.
  - Records model training-scope metadata.
- `src/xenix/services/ml_service.py`
  - Follow-up evaluate tasks now prefer `evaluation_model_artifact_path` and fall back to canonical model path for older payloads.
- `src/xenix/services/trained_model_metadata.py`
  - Bumped metadata schema to `4`.
  - Added evaluation/apply model training scope fields.
- `docs/20-product-tdd/ml-task-lifecycle.md`
  - Documented split-trained evaluation model vs all-row final apply model lifecycle semantics.
- `docs/20-product-tdd/runtime-boundaries.md`
  - Documented Agent-facing consequence that holdout metrics and apply artifact now have distinct model scopes.
- `tests/test_ml_execution.py`
  - Added assertions that fit and semi-supervised flows register the final apply model while evaluating the split-trained model.

### Verification Results

- Passed: `pdm run pytest tests/test_ml_execution.py::test_dataset_scoped_fit_evaluate_and_apply_run tests/test_ml_execution.py::test_semisupervised_classifier_uses_partial_target_and_labeled_holdout tests/test_ml_execution.py::test_bulk_tuning_creates_one_tuning_task_per_model_and_follow_up_evaluations`
- Passed: `pdm run pytest tests/test_ml_execution.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py`
- Passed: `pdm run pytest tests/test_ml_registry.py`
- Passed: `pdm run check`

### Scope Decision

- User agreed to Slice 4A:
  - adjust LightGBM classification default tuning grid to the compact teaching-script shape;
  - defer final-refit behavior to another slice.
- No source changes yet; waiting for explicit start before mutating durable code.

### Implemented Source Changes

- `src/xenix/services/ml/models/classification.py`
  - Narrowed `LightGBMClassificationParamGrid` to the compact teaching-script active grid:
    - `n_estimators=[100, 200]`
    - `max_depth=[-1, 5, 10]`
  - Kept manual LightGBM classification params unchanged so explicit larger grids remain possible.
- `tests/test_ml_registry.py`
  - Added assertions that the default LightGBM classification grid contains only the compact default dimensions.

### Verification Results

- Passed: `pdm run pytest tests/test_ml_registry.py`
- Passed: `pdm run pytest tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_exposes_catalog_without_train_enums`
- Passed: `pdm run check`

## Slice 4B - Final Refit Apply Model

### Task Packet Changes

- Recorded the lifecycle problem found in the current implementation:
  - the model registered for apply is currently the holdout-split training model;
  - follow-up evaluation also uses that same artifact.
- Recorded the proposed contract:
  - evaluation model remains trained on the train split and evaluated on holdout;
  - apply model is refit on all eligible training rows and becomes the canonical trained model artifact;
  - metadata records the distinction.

### Source Changes

- None. Source mutation is waiting for explicit start after Impact Handshake.

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

## Slice 4 - Learn From Teaching Model Usage And Parameters

### Task Packet Changes

- Recorded exploration findings from `ml/classification/light_gbm_classification_model/light_gbm_classification_model.py`.
- Recorded exploration findings from `ml/regression/light_gbm/light_gbm.py`.
- Recorded cross-model teaching-script pattern: tune/evaluate on split, then retrain final model on all data with best params for prediction.

### Source Changes

- None. Source mutation is waiting for explicit user start after scope confirmation.

### Verification

- Not run for this slice yet.

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

## Slice 5 - Text Analysis Capability Intake

### Task Packet Changes

- Recorded the current `assets/text_analysis` bundle as a demo/reference input rather than a direct product contract.
- Mapped the demo bundle into capability atoms and separated:
  - analysis-flow capabilities better served by `data.query` / `data.transform` / `analysis.graph`;
  - candidate model/analyzer capabilities that may belong in the ML catalog.
- Recorded the recommended first intake order:
  - text classification;
  - text clustering;
  - topic modeling;
  - text similarity retrieval.
- Recorded that sentiment/aspect-sentiment/summarization/information-extraction are currently heuristic demo outputs and should not be promoted blindly.

### Source Changes

- None. Source mutation is waiting for explicit user start.

### Verification

- Not run. No durable code or docs changed in this slice.

## Slice 6 - Clustering Analysis Capability Intake

### Task Packet Changes

- Recorded findings from `tasks/ml-service-optimizations/assets/clustering_analysis`.
- Compared asset model coverage and evaluation outputs against the native clustering catalog.
- Recorded that MiniBatchKMeans, Birch, and GaussianMixture are the strongest new model candidates because they support new-row prediction.
- Recorded that predictable clustering `apply` support is the highest-value usage improvement.
- Recorded that non-predictable segmenters such as Agglomerative, Spectral, DBSCAN, and OPTICS need honest train-only/catalog semantics before broader promotion.

### Source Changes

- `src/xenix/services/ml/models/base.py`
  - Implemented native clustering apply support for estimators whose persisted pipeline exposes `predict`.
  - Apply outputs `cluster_predictions.csv` and appends `cluster_id`.
- `src/xenix/services/ml/models/clustering.py`
  - Added `clustering.minibatch_kmeans`.
  - Added `clustering.birch`.
  - Added `clustering.gaussian_mixture`.
- `src/xenix/services/ml/registry.py`
  - Registered the new clustering services.
- `tests/test_ml_registry.py`
  - Updated catalog size and added metadata assertions for the new clustering services.
- `tests/test_ml_execution.py`
  - Added clustering apply coverage.
  - Added fit/export coverage for MiniBatchKMeans, Birch, and GaussianMixture.
- `tests/test_agent_harness_first_slice.py`
  - Updated clustering metadata directory expectations.

### Verification

- Read asset scripts, config, evaluation JSON, preprocessing guide, and extracted docx text.
- Read native clustering service, registry, base service, and targeted tests.
- Ran `pdm run python` to verify sklearn `fit_predict`/`predict` support for candidate clustering estimators.
- Passed: `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py::test_clustering_fit_runs_without_follow_up_evaluate_and_persists_export_artifact tests/test_ml_execution.py::test_new_predictable_clustering_models_fit_and_persist_export_artifact tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_directory_queries_return_lightweight_summaries`
- Passed: `pdm run pytest tests/test_ml_execution.py tests/test_agent_harness_first_slice.py`
- Passed: `pdm run check`
