# Discussion Log

## Slice 1 - Expand Evaluation Metrics

### User Claim

- ML Service evaluation should not rely on a single primary metric.
- Classification teaching materials include: accuracy, balanced accuracy, macro/weighted precision/recall/F1, confusion matrix, classification report, ROC AUC, PR AUC, log loss.
- Regression teaching materials include: MSE, RMSE, MAE, R2, MAPE, explained variance, residual mean, residual standard deviation.

### Initial Classification

- Intent: improve ML Service evaluation behavior and surfaced evaluation evidence.
- Durable owner likely: `src/xenix/services/ml/`, with possible UI/storage/test blast radius to be confirmed.
- Current mode: Explore, then Solidify before any source mutation.

### Guardrails

- Do not modify source code until the user explicitly says to start implementation.
- Use teaching materials as reference input, not as direct durable truth until verified against existing ML Service contracts.
- Preserve non-technical user friendliness: metrics should support business interpretation, not only technical completeness.

### Open Questions

- Which existing evaluation surface consumes the current primary metric: service result model, storage record, UI, or all of them?
- Should all metrics be persisted, displayed, or only computed for internal selection/reporting?
- How should binary-only metrics such as ROC AUC, PR AUC, and log loss behave for multiclass or estimators without probability output?

### Next Step

- Inspect existing ML Service evaluation flow and the teaching reference directories once available in the task packet.

### Exploration Findings

- Local ML guidance says evaluation policy ownership belongs in `src/xenix/services/ml/evaluation.py`.
- Current regression metrics: `r2`, `rmse`, `mae`.
- Current classification metrics: `accuracy`, `precision_weighted`, `recall_weighted`, `f1_weighted`.
- `CandidateMetrics.metrics` is currently `dict[str, float]`, so it can carry additional scalar metrics but cannot carry confusion matrix or classification report without a contract change.
- Trained model metadata also stores `evaluation_metrics: dict[str, float]`, so persisted model metadata has the same scalar-only limitation.
- Evaluation execution happens in `NumericAndCategoricalModelService.evaluate()`: it loads the trained estimator and holdout frame, predicts `y_pred`, then calls `build_metric_snapshot(...)`.
- Probability-dependent metrics such as ROC AUC, PR AUC, and log loss are not available from `y_pred`; they need probability or decision scores from the estimator when supported.

### Candidate Slice Shape

- Keep `primary_metric_name` / `primary_metric_value` for ranking and backward-compatible summaries.
- Expand scalar metrics first:
  - Regression: add `mse`, `mape`, `explained_variance`, `residual_mean`, `residual_std`.
  - Classification: add `balanced_accuracy`, `precision_macro`, `recall_macro`, `f1_macro`.
- Add optional structured evaluation details for classification:
  - `confusion_matrix`
  - `classification_report`
  - probability metric availability notes
- Treat ROC AUC, PR AUC, and log loss as conditional metrics:
  - compute only when estimator exposes usable probabilities or scores;
  - avoid pretending unsupported metrics are zero;
  - record omission reason in details rather than hiding the condition.

### Impact Handshake Draft

- Address and Object:
  - `src/xenix/services/ml/evaluation.py`: metric builders and comparison direction map.
  - `src/xenix/services/ml/contracts.py`: `CandidateMetrics` shape if structured details are accepted.
  - `src/xenix/services/ml/models/base.py`: pass probability/score context into classification metrics if needed.
  - `src/xenix/services/trained_model_metadata.py`: persisted evaluation metadata projection if structured details are retained.
  - `tests/test_ml_registry.py` and/or `tests/test_ml_execution.py`: recurrence guards.
- State Diff:
  - From: scalar-only minimal evaluation metrics, with one primary metric used for ranking.
  - To: scalar metric set expanded, with optional structured classification evaluation evidence and conditional probability metrics.
- Blast Radius Forecast:
  - ML task result payload shape, trained-model metadata payload, Agent/UI surfaces that display stored metrics.
- Invariants Check:
  - Primary metric remains stable for model comparison.
  - Training/tuning selection still uses a scikit-learn scoring name compatible with `GridSearchCV`.
  - Unsupported probability metrics are not fabricated.
  - Existing persisted metadata remains parseable.
- Verification:
  - Unit tests for regression metric completeness.
  - Unit tests for classification metric completeness.
  - Test that structured classification details serialize in evaluate result.
  - Existing ML execution tests still pass.

### Presented Impact Handshake

- Slice 1 is scoped as evaluation-result enrichment, not model-selection redesign.
- The proposed contract keeps scalar metrics as the ranking/comparison surface and adds structured evaluation details separately.
- Probability-dependent classification metrics are conditional facts, not required facts.

### Scope Expansion From User

- User clarified that this task is not constrained to ML Service only.
- Agent tools and other related modules may be included when that produces a better user-facing evaluation workflow.

### Expanded Exploration Findings

- Agent tools are implemented in `src/xenix/services/agent/tools.py`.
- `model.train` / `model.hyper_train` wait for follow-up evaluation when it is required, so training tool results can surface evaluated trained-model metadata once available.
- `model.task.query` currently includes full task `result_payload` under `result`, so richer evaluation payloads are already mechanically exposed to the Agent.
- `model.task.query` markdown currently lists task status, error, and follow-up task ids, but does not summarize evaluation metrics for the user.
- Tool presentations do not need metric-specific changes for this slice.

### Expanded Candidate Slice Shape

- ML evaluation layer:
  - compute complete scalar metrics;
  - produce structured details for confusion matrix, classification report, and metric availability.
- Persistence projection:
  - keep `evaluation_metrics` scalar-only for stable sorting and compact model metadata;
  - add an optional `evaluation_details` metadata field only if structured details need durable reuse outside task result payloads.
- Agent tool projection:
  - keep raw `result` payload intact for machine-readable inspection;
  - add a compact evaluation summary to `model.task.query` markdown when a queried task is an evaluation task with completed metrics;
  - expose probability metric unavailable reasons in payload/details so the Agent can explain missing ROC/PR/log loss honestly.

### Expanded Impact Handshake

- Address and Object:
  - `src/xenix/services/ml/evaluation.py`: metric builders, structured detail construction, metric direction map.
  - `src/xenix/services/ml/contracts.py`: `CandidateMetrics` contract, likely adding `details: dict[str, Any]`.
  - `src/xenix/services/ml/models/base.py`: estimator probability/score extraction for classification evaluation.
  - `src/xenix/services/trained_model_metadata.py`: scalar metrics projection and optional structured detail projection.
  - `src/xenix/services/agent/tools.py`: `model.task.query` user-facing summary for evaluation results.
  - Tests under `tests/test_ml_registry.py`, `tests/test_ml_execution.py`, and Agent tool tests if existing coverage targets tool payload/markdown.
- State Diff:
  - From: evaluation exists but user-facing tool summaries do not explain the metric set; task payload has minimal scalar metrics.
  - To: ML task payload carries richer evaluation evidence, trained model metadata preserves stable scalar summary, Agent tool output can explain multi-metric evaluation.
- Blast Radius Forecast:
  - ML task payload schema, trained model metadata schema, Agent model task query payload/markdown, tests that assert result payload shape.
- Invariants Check:
  - Existing primary metric semantics remain stable.
  - Agent tool schemas for inputs do not expand unless needed; this slice is output enrichment.
  - Existing raw `result` payload remains JSON-serializable.
  - Old trained-model metadata remains parseable.
  - User-visible text stays business-friendly and does not dump large reports blindly into markdown.
- Verification:
  - Direct metric builder tests.
  - ML execution test for persisted metadata.
  - Agent tool/query test proving evaluation summary is visible without losing raw details.

### Execution Notes

- Implementation kept `metrics` scalar-only and added `details` for structured evidence.
- Agent-facing output now has two layers:
  - machine-readable raw evaluation payload under `model.task.query` result;
  - compact markdown summary for primary/key metrics.
- Probability-dependent classification metrics are represented as conditional evidence:
  - computed when `predict_proba` is available and compatible;
  - otherwise omitted from scalar metrics and explained in `details.probability_metrics`.
- Regression currently has no structured details beyond scalar residual metrics.

### Slice 1 Result

- The training/evaluation chain now exposes broader evidence without changing model-selection primary metric behavior.
- The Agent can show a concise metric summary while still retaining structured details for deeper inspection.

## Slice 2 - Fix Apply / Inference Naming Drift

### User Claim

- Forward-looking contract uses `apply`, not `inference`.
- Existing durable docs already state legacy `inference` names are migration inputs only.
- Code-level abstractions still contain substantial `inference` naming residue.

### Initial Classification

- Constraint: product contract and durable terminology are already decided; implementation names should align with the contract.
- Current mode: Explore, then Solidify before source mutation.
- Durable owners:
  - ML task lifecycle and execution: `src/xenix/services/ml/`, `src/xenix/services/ml_task_service.py`, `src/xenix/services/ml_service.py`.
  - Agent-facing tool contract: `src/xenix/services/agent/tools.py`.
  - Storage migration compatibility: `src/xenix/services/storage/migrations.py`.

### Governing Anchors

- `docs/20-product-tdd/ml-task-lifecycle.md`: new service and Agent contracts use `apply`; legacy persisted task rows or tests using `inference` are migration inputs only.
- `docs/20-product-tdd/runtime-boundaries.md`: forward-looking tool contracts use `apply`, not `inference`; legacy `inference` names are migration inputs only.
- `docs/20-product-tdd/storage-ownership.md`: legacy inference task values are outside the current implemented baseline.

### Exploration Findings

- Already aligned:
  - `MLTaskType.APPLY` persists the forward task type.
  - Agent tool is `model.apply`.
  - `MLService.apply(...)` and `ApplyWithFilesInput` are already forward-named.
  - Artifact kind is `apply_result`.
- Naming drift to fix:
  - `InferenceInputFile`, `InferenceModelPayload`, `InferenceTaskRequest`, `InferenceSummary`, `InferenceTaskResult` in `src/xenix/services/ml/contracts.py`.
  - `ModelServiceBase.infer(...)` in `src/xenix/services/ml/types.py`.
  - `infer(...)` implementations in supervised, association, and recommendation model services.
  - `run_inference_task(...)` operation entrypoint and logs in `src/xenix/services/ml/operations/__init__.py`.
  - `MLTaskService._resolve_entrypoint(...)` maps `MLTaskType.APPLY` to `run_inference_task`.
  - `_finalize_apply_task(...)` validates `InferenceTaskResult`.
  - `remote_worker.ENTRYPOINTS` exposes `run_inference_task`.
  - Agent/task detail helper still checks request payload key `inference_model`.
  - `tests/test_ml_workers.py` imports and runs `run_inference_task`.
- Likely keep as legacy/migration:
  - `src/xenix/services/storage/migrations.py` mappings from `inference` to `apply`.
  - `tests/test_storage_bootstrap.py::test_storage_bootstrap_migrates_v7_inference_values_to_apply`.
  - Translation vanished strings and old UI class names are likely historical/legacy unless this slice explicitly expands into UI cleanup.
- Borderline tactical naming:
  - `MaterializeManualInferenceCsvInput`, `materialize_manual_inference_csv`, and temp dir `manual-inference` in `DatasetService` are still called from apply inline-row materialization; likely should become apply-named wrappers with legacy aliases only if tests or other callers require them.

### Candidate Slice Shape

- Rename forward ML apply contracts and model-service API:
  - `Inference*` -> `Apply*`.
  - `inference_model` payload key -> `apply_model`.
  - `infer(...)` -> `apply(...)`.
  - `run_inference_task(...)` -> `run_apply_task(...)`.
- Preserve backwards compatibility only at migration/legacy-read seams:
  - storage migrations retain `inference` value handling;
  - task request parsing may accept old `inference_model` only as a compatibility alias if needed for old task rows or remote worker artifacts.
- Update tests away from `inference` naming except migration tests.

### Open Questions

- Should this slice include DatasetService manual inline file materialization naming (`manual_inference`) or leave it for a smaller UI/data-service cleanup slice?
- Should remote worker entrypoint keep `run_inference_task` as a compatibility alias for already-staged remote commands, or can it be removed because task execution always uses the current local entrypoint name?

### User Decision

- No backward compatibility alias is needed for old apply payload or worker entrypoint names because the software has not been officially released.
- Therefore do not preserve:
  - `inference_model` as a validation alias for `apply_model`;
  - `run_inference_task` as a legacy alias for `run_apply_task`.

### Revised Candidate Slice Shape

- Do a clean forward rename:
  - `Inference*` contract classes become `Apply*`.
  - request/result payload key becomes `apply_model`.
  - model adapter method becomes `apply(...)`.
  - worker entrypoint becomes `run_apply_task`.
- Keep `inference` only where it is explicitly historical:
  - storage migrations;
  - storage migration tests;
  - OpenInference observability standard names;
  - vanished translations unless this slice intentionally runs i18n cleanup.
- Include DatasetService inline apply materialization naming in this slice unless implementation evidence shows the UI/data-service rename would create unrelated churn:
  - `MaterializeManualInferenceCsvInput` -> `MaterializeManualApplyCsvInput`;
  - `materialize_manual_inference_csv` -> `materialize_manual_apply_csv`;
  - temp directory `manual-inference` -> `manual-apply`.

### Execution Notes

- Implemented as clean rename without compatibility aliases.
- Included DatasetService manual inline apply CSV materialization naming.
- Renamed the unused row editor widget file/class to apply terminology rather than deleting it.
- Kept storage migration references to `inference` because those are legacy input normalization.
- Kept `dataset_inspection.infer_column_kind` because it refers to schema/type inference, not model apply.

### Addendum - Apply Input Artifact/Dataset References

- User reported Agent called `model.apply` with `input_files: ["artifact://..."]` and received `Dataset source path must point to an existing file.`
- Root cause:
  - provider-facing Agent instructions tell the Agent to use artifact links rather than invent local paths;
  - `model.apply` accepted `input_files` as strings but passed them directly into `MLService.apply`;
  - `MLService.apply` treated each string as a local filesystem path.
- Decision:
  - resolve Agent-safe input references at the Agent tool boundary before entering `MLService`;
  - keep `MLService.apply` operating on resolved local file paths for worker execution;
  - support both `artifact://...` and registered dataset ids in `model.apply.input_files`;
  - preserve local absolute/path-like strings for internal and developer workflows.
- Implementation:
  - `AgentToolRegistry._model_apply` now normalizes `input_files` through `_resolve_apply_input_files`.
  - `artifact://...` values resolve through `ArtifactService.resolve_uri`.
  - dataset id values resolve through `DatasetService.get_dataset`.
  - path-like values continue unchanged.

### Slice 2 Result

- Forward ML apply contracts, worker entrypoints, model adapter API, Agent/UI task payload projection, and inline apply CSV helper now use apply terminology.
- The code path no longer exposes `Inference*`, `inference_model`, `run_inference_task`, or model-service `infer(...)` outside explicitly historical/external contexts.
- Agent `model.apply` can now accept artifact links or dataset ids as apply input sources.

### Addendum - `input_files` Naming Drift

- User noted `input_files` is misleading now that `model.apply` accepts artifact links and dataset ids.
- Current shape:
  - Agent-facing `model.apply.input_files` accepts strings that may be local paths, `artifact://...`, or dataset ids.
  - Agent tool resolves those strings to local paths before calling `MLService.apply`.
  - Worker-facing `ApplyTaskRequest.input_files` contains resolved `ApplyInputFile` objects with `absolute_path`, so that internal name remains accurate.
- Proposed correction:
  - Rename provider-facing Agent tool parameter from `input_files` to `input_sources`.
  - Rename Agent normalization helpers from `_resolve_apply_input_files` to `_resolve_apply_input_sources`.
  - Rename `MLService` service input object from `ApplyWithFilesInput` to `ApplyInputSourcesInput` only if we want the service boundary to accept artifact/dataset ids directly.
- Boundary preference:
  - Agent-facing contract should use `input_sources`.
  - Worker-facing task request can keep `input_files` because it is already resolved to concrete files.
  - `input_rows` remains accurate for inline row payloads.

### User Decision - No Raw Path Apply Inputs

- Agent-facing `model.apply` must not accept raw local paths or path-like strings.
- Reason: operating on a user-visible but unregistered path violates the privacy boundary; Agent tools should only act on files the user has explicitly provided through service-managed registration.
- Allowed Agent-facing apply sources:
  - `artifact://...`
  - registered dataset ids
  - inline `input_rows`
- Disallowed Agent-facing apply sources:
  - absolute filesystem paths
  - relative/path-like strings

### Final Apply Input Source Decision

- Implemented `model.apply.input_sources` as the Agent-facing source field.
- `input_sources` accepts only registered dataset ids and `artifact://...` URIs.
- Raw filesystem paths are rejected at the Agent tool boundary.
- Internal `MLService.apply` and worker `ApplyTaskRequest` still use resolved `input_files` because they operate after source authorization and URI/dataset resolution.

## Slice 3 - Expand Supervised Model Catalog

### User Claim

- Classification candidates worth adding:
  - `ExtraTreesClassifier`
  - `HistGradientBoostingClassifier`
  - `SVC`
  - `LinearSVC + CalibratedClassifierCV`
  - `MLPClassifier`
  - `MultinomialNB`
  - `LabelPropagation`
  - `LabelSpreading`
  - `SelfTrainingClassifier`
- Regression candidates worth adding:
  - `ElasticNet`
  - `SVR`
  - `MLPRegressor`
  - `HistGradientBoostingRegressor`

### Initial Classification

- Intent: expand the canonical model catalog exposed to ML Service, UI schema forms, and Agent `model.metadata`.
- Current mode: Explore/Solidify before mutation.
- Durable owner:
  - model service definitions under `src/xenix/services/ml/models/`;
  - canonical registry under `src/xenix/services/ml/registry.py`;
  - Agent-facing model discovery indirectly through `model.metadata`.

### Exploration Findings

- Existing native model services already cover the teaching directories under `ml/classification` and `ml/regression`; the requested models are not direct script migrations from those directories.
- Model catalog entries are Pydantic-driven and become Agent-visible through `model.metadata`.
- Recommendation order is controlled by `recommendation_tier`, so adding many models changes Agent candidate ordering, not only backend capability.
- Existing supervised model service assumes:
  - one complete target column;
  - train/test split evaluation;
  - feature preprocessing through numeric/categorical selectors and one-hot encoding;
  - probability metrics are available only if the trained estimator exposes `predict_proba`.

### Candidate Inclusion Decision

- Include in this slice:
  - `classification.extra_trees`
  - `classification.hist_gradient_boosting`
  - `classification.svc`
  - `classification.linear_svc_calibrated`
  - `classification.mlp`
  - `classification.multinomial_naive_bayes`
  - `regression.elastic_net`
  - `regression.svr`
  - `regression.mlp`
  - `regression.hist_gradient_boosting`
- Defer:
  - `LabelPropagation`
  - `LabelSpreading`
  - `SelfTrainingClassifier`
- Reason for deferral:
  - They are semi-supervised models, but the current product/service contract has no durable role semantics for partially labeled rows or an unlabeled sentinel.
  - Treating them as ordinary fully supervised classifiers would add catalog surface while hiding the most important evidence boundary.
  - A later semi-supervised slice should define target role semantics, unlabeled value handling, evaluation split policy, and Agent guidance.

### Candidate Implementation Shape

- Add shallow Pydantic parameter and grid schemas matching current UI form constraints.
- Keep estimator wrappers local to classification/regression modules when a shallow schema needs translation:
  - MLP `hidden_layer_size` -> sklearn `hidden_layer_sizes=(...)`.
  - Calibrated LinearSVC builds `CalibratedClassifierCV(estimator=LinearSVC(...))`.
  - MultinomialNB overrides preprocessing to keep numeric/categorical features non-negative.
- Use dense preprocessing for histogram gradient boosting where required by sklearn dense-input expectations.
- Keep worker parallelism conservative with `n_jobs=1` where supported.
- Add smoke tests for representative new classifiers/regressors instead of full execution tests for every model.

### Scope Pivot - Support Semi-Supervised Binding Roles

- User proposed expanding bind roles now so semi-supervised learning can be represented honestly.
- Current binding implementation already persists role-shaped snapshots, but supervised execution still projects them into `feature_columns` and `target_columns`.
- Current supervised base class requires exactly one complete target column through the `target` role.
- Semi-supervised models should not be added as ordinary classifiers because they need a distinct contract:
  - feature columns;
  - a partial label/target column;
  - a rule for which rows are unlabeled;
  - evaluation on held-out labeled rows only, while unlabeled rows may participate in training.

### Revised Semi-Supervised Contract Candidate

- Add a semi-supervised classifier service base rather than widening the ordinary supervised base.
- Semi-supervised model catalog entries declare a train role schema with:
  - `feature`: many columns, required;
  - `partial_target`: one column, required; values may be blank/null to represent unlabeled rows.
- Apply role schema remains `feature` only.
- The semi-supervised base projects `partial_target` to scikit-learn labels by:
  - treating missing/blank cells as unlabeled;
  - encoding unlabeled rows as `-1` for sklearn;
  - splitting only labeled rows into train/holdout;
  - fitting on labeled-train rows plus unlabeled rows;
  - evaluating only on labeled holdout rows.
- Defer custom unlabeled sentinel values and separate indicator-column support unless product pressure appears.

### Execution Notes

- Implemented semi-supervised classification as a separate model-service base.
- Ordinary supervised models still declare and require `feature + target`.
- Semi-supervised classifiers declare `feature + partial_target`.
- Blank/null `partial_target` cells are treated as unlabeled rows.
- The training split holds out only labeled rows; unlabeled rows are added to the training side and never counted as evaluation evidence.
- Added three semi-supervised classifiers:
  - `classification.label_propagation`
  - `classification.label_spreading`
  - `classification.self_training`
- Hyperparameter tuning is disabled for the initial semi-supervised services because the current CV flow would treat unlabeled rows as scoring labels unless a separate semi-supervised tuning policy is designed.

### Ordinary Supervised Model Expansion

- After the semi-supervised role contract landed, continued with the ordinary supervised catalog additions from the original Slice 3 request.
- Added classification models:
  - `classification.extra_trees`
  - `classification.hist_gradient_boosting`
  - `classification.svc`
  - `classification.linear_svc_calibrated`
  - `classification.mlp`
  - `classification.multinomial_naive_bayes`
- Added regression models:
  - `regression.elastic_net`
  - `regression.svr`
  - `regression.mlp`
  - `regression.hist_gradient_boosting`
- Kept schemas shallow for UI/Agent rendering.
- MLP services expose `hidden_layer_size` and map it to sklearn `hidden_layer_sizes=(...)` internally.
- SVC enables probability output so expanded classification evaluation evidence can include probability-dependent metrics.
- Calibrated LinearSVC uses `CalibratedClassifierCV` so it exposes `predict_proba`.
- MultinomialNB overrides preprocessing to keep numeric/categorical features non-negative.

## Slice 4 - Learn From Teaching Model Usage And Parameters

### User Claim

- Teaching materials include concrete model usage and parameter settings.
- There may be worth-learning implementation details, especially a claim that LightGBM usage has better performance.

### Initial Classification

- Intent: evaluate whether teaching-script model usage should influence native ML Service defaults, tuning grids, preprocessing, or lifecycle.
- Current mode: Explore; no source mutation yet.
- Durable owner candidates:
  - model parameter schemas in `src/xenix/services/ml/models/`;
  - evaluation/tuning policy in `src/xenix/services/ml/evaluation.py`;
  - training lifecycle in `src/xenix/services/ml/models/base.py`;
  - Agent-facing model metadata in `src/xenix/services/agent/tools.py` if defaults/guidance change.

### Exploration Findings

- LightGBM classification teaching script:
  - avoids normalization because LightGBM is tree-based;
  - dynamically chooses `objective="binary"` vs `objective="multiclass"` plus `num_class`;
  - uses `verbose=-1` / `verbosity=-1`;
  - uses a deliberately simplified active grid: `n_estimators=[100, 200]`, `max_depth=[-1, 5, 10]`;
  - leaves broader grid dimensions as commented optional parameters.
- LightGBM regression teaching script:
  - uses `objective="regression"`;
  - uses `n_jobs=-1`;
  - uses grid values that mostly match the current native regression LightGBM grid:
    - `num_leaves=[15, 31, 63]`
    - `max_depth=[-1, 3, 5, 7]`
    - `learning_rate=[0.01, 0.05, 0.1]`
    - `n_estimators=[100, 200, 300]`
    - `subsample=[1.0, 0.8]`
    - `colsample_bytree=[1.0, 0.8]`
- Current native LightGBM implementation already:
  - does not scale numeric features;
  - silences LightGBM logs;
  - sets objective for regression;
  - exposes probability output through `predict_proba`.
- Current native LightGBM classification grid is broader than the active teaching grid.
- Teaching scripts generally tune on a train split, evaluate on test split, then retrain a final model on all data with the best params for prediction.
- Current native supervised fit/tune saves the model trained on the training split because the same artifact is later evaluated against holdout.

### Candidate Lessons

- Safe local LightGBM lesson:
  - consider making the default LightGBM classification tuning grid smaller or tiered, because the teaching script intentionally keeps the active grid compact for runtime.
- Not a direct copy:
  - `n_jobs=-1` may improve single-script performance but can oversubscribe when Xenix worker pool dispatches multiple tasks; it should be governed by worker resource policy, not copied into every estimator.
  - dynamic LightGBM classification objective is useful as explicitness, but sklearn `LGBMClassifier` generally handles objective inference; adding it may require a wrapper that sees labels at fit time.
- Larger lifecycle lesson:
  - separate "evaluated candidate model" from "final apply model retrained on all eligible rows" if we want production predictions to use all data while preserving honest holdout evidence.
  - this is cross-model training lifecycle work, not LightGBM-only tuning.

### User Decision

- Proceed with Slice 4A:
  - narrow the default LightGBM classification tuning grid to match the teaching script's compact active grid;
  - keep larger LightGBM classification search spaces available through explicit user/Agent-provided `model.hyper_train` grids.
- Defer final-refit behavior to a separate future slice because it changes the training/evaluation/apply artifact lifecycle.

## Slice 4B - Final Refit Apply Model

### User Claim

- Continue with final-refit as a separate slice.

### Initial Classification

- Intent: improve training lifecycle so the model used for apply can learn from all eligible training rows while evaluation remains holdout-based and honest.
- Current mode: Explore/Solidify before source mutation.
- Durable owners:
  - supervised model worker behavior in `src/xenix/services/ml/models/base.py`;
  - fit/tune task result contracts in `src/xenix/services/ml/contracts.py`;
  - trained model registration/finalization in `src/xenix/services/ml_task_service.py`;
  - follow-up evaluation routing in `src/xenix/services/ml_service.py`;
  - trained model metadata in `src/xenix/services/trained_model_metadata.py`.

### Current Lifecycle Finding

- `NumericAndCategoricalModelService.fit()` and `tune()` split the dataset into train/holdout.
- The estimator trained on the training split is dumped to `model_artifact_path`.
- `MLTaskService` copies that same artifact to the canonical trained-model path.
- `MLService._submit_follow_up_evaluation()` evaluates the canonical trained-model path against the holdout artifact.
- Therefore the current apply model is the holdout-split candidate model, not a final model refit on all eligible training rows.

### Desired Contract

- Keep two model artifacts for supervised fit/tune:
  - evaluation model: trained on the training split, evaluated on holdout;
  - apply model: refit on all eligible rows with the accepted params/best params, registered as the canonical trained model.
- Follow-up evaluate task must use the evaluation model artifact, not the final apply model.
- Trained model row `artifact_path` should point to the final apply model.
- Evaluation metadata still attaches to the trained model row, but should be understood as evidence from the holdout-split evaluation model with the same params/training recipe.

### Candidate Implementation Shape

- Extend `FitTaskResult` and `HyperparameterTuningTaskResult` with optional `final_model_artifact_path`.
- For ordinary supervised `fit()`:
  - train/evaluate candidate on train split as today;
  - train a fresh final pipeline on full `X, y`;
  - dump final pipeline to `final_model_artifact_path`;
  - write key-driver report from the final apply model.
- For ordinary supervised `tune()`:
  - run GridSearchCV on training split as today;
  - preserve `search.best_estimator_` as the evaluation model;
  - refit that configured best estimator on full `X, y`;
  - dump it to `final_model_artifact_path`.
- For semi-supervised classification:
  - keep holdout labeled rows out of the evaluation model;
  - train final apply model on all rows, including all labeled and unlabeled rows.
- In `MLTaskService` finalization:
  - canonical trained model path copies `final_model_artifact_path` when present;
  - result payload records `evaluation_model_artifact_path` for follow-up evaluation;
  - fallback remains compatible when no final model path exists.
- In `MLService._submit_follow_up_evaluation()`:
  - prefer `evaluation_model_artifact_path`;
  - fallback to `canonical_model_artifact_path` for older/non-refit results.
- Metadata should record the training scope distinction, likely:
  - `apply_model_training_scope="all_eligible_rows"`;
  - `evaluation_model_training_scope="holdout_train_split"`.

### Guardrails

- Do not evaluate the all-row final model on the same holdout labels; that would be leakage.
- Do not change unsupervised summary models in this slice.
- Do not change Agent tool inputs.
- Preserve task payload parseability for task rows that lack `final_model_artifact_path`.

### Execution Notes

- Added `final_model_artifact_path` to fit and tuning task results.
- Ordinary supervised fit/tune now produce:
  - an evaluation model trained on the train split;
  - a final apply model trained on all eligible rows.
- Semi-supervised fit now produces:
  - an evaluation model trained on training-side labeled rows plus unlabeled rows;
  - a final apply model trained on all labeled and unlabeled rows.
- `MLTaskService` registers the final apply model as the canonical trained model artifact.
- Follow-up evaluate tasks use `evaluation_model_artifact_path`, not the canonical apply model.
- Trained model metadata now records:
  - `evaluation_model_training_scope="holdout_train_split"`;
  - `apply_model_training_scope="all_eligible_rows"`.

## Slice 5 - Text Analysis Capability Intake

### User Claim

- Organize `tasks/ml-service-optimizations/assets/text_analysis`.
- The core goal is to bring several text-analysis model capabilities into the native product surface instead of leaving them as an isolated demo bundle.

### Initial Classification

- Intent: introduce new productized analysis/model capability around text data.
- Current mode: Explore first; do not mutate durable source until the user explicitly says to start.
- Likely durable owners:
  - model catalog and execution contracts under `src/xenix/services/ml/`;
  - Agent-facing model metadata and tool projection under `src/xenix/services/agent/tools.py`;
  - durable capability wording under `docs/20-product-tdd/` and `docs/30-unit-tdd/`.

### Exploration Findings

- `tasks/ml-service-optimizations/assets/text_analysis/02_text_analysis_all.py` is one monolithic demo pipeline, not a product contract.
- The demo bundle currently covers these capability atoms:
  - text cleaning and Chinese segmentation via `jieba`;
  - word frequency;
  - TF-IDF keywords;
  - word cloud;
  - co-occurrence pairs;
  - lexicon-style sentiment;
  - aspect sentiment;
  - LDA topic keywords;
  - TF-IDF + KMeans text clustering;
  - TF-IDF + logistic-regression text classification;
  - TF-IDF cosine-similarity retrieval;
  - simple extractive summary;
  - rule-based information extraction.
- Current native ML Service does not yet have a text-analysis family or text-vectorization pipeline.
- Existing catalog is still centered on:
  - supervised tabular models;
  - clustering/anomaly analyzers;
  - association rules;
  - rating-style recommendation.
- Some demo outputs should not be forced into the model catalog because they are better expressed as data-analysis flows:
  - word frequency;
  - TF-IDF keyword ranking;
  - co-occurrence tables;
  - word cloud rendering.
- Some demo outputs are closer to productizable analyzer/model capabilities:
  - topic modeling;
  - text clustering;
  - text classification;
  - text similarity retrieval.
- Some demo outputs are currently heuristic and would need a stronger product contract before being called “model capabilities”:
  - lexicon sentiment;
  - aspect sentiment;
  - extractive summary;
  - rule-based information extraction.

### First-Principles Recommendation

- Separate “text analysis workflow” from “model catalog” instead of porting the demo script as-is.
- Keep frequency/keyword/word-cloud/co-occurrence in the data-analysis + graphing stack.
- Introduce productized text model capability only where the current ML Service shape can defend it:
  - vectorize text;
  - fit/store/apply a model or analyzer;
  - return bounded structured outputs.
- Recommended first intake slice:
  - text classification with TF-IDF + supervised classifier;
  - text clustering with TF-IDF + KMeans;
  - topic modeling with vectorizer + LDA;
  - text similarity retrieval with stored vectorizer/index contract.
- Defer sentiment/aspect-summary/extraction until the dependency and output contracts are explicit enough to avoid a pile of brittle heuristics in the durable model catalog.

### Open Questions

- Should these be exposed as a new `text_analysis` model family, or should they be folded into existing family names with text-specific guidance?
- What is the minimal input contract:
  - one text column only;
  - optional id column;
  - optional label column for supervised text classification?
- Is Chinese-first tokenization acceptable as the initial scope, or must the first contract be multilingual?
- Should `jieba` become a durable dependency, or should tokenization stay pluggable behind a service-owned adapter?

### Recommended Next Step

- If the user says to start implementation, do an Impact Handshake for the first intake slice before mutating source:
  - likely start with text classification + text clustering + topic modeling;
  - leave sentiment/summarization/extraction for a later contract-driven slice.

## Slice 6 - Clustering Analysis Capability Intake

### Objective & Hypothesis

- Objective: inspect `tasks/ml-service-optimizations/assets/clustering_analysis` for clustering models or usage improvements worth introducing into native ML Service.
- Hypothesis: the asset bundle is useful as model-selection and workflow evidence, but should not be copied directly because native Xenix already owns preprocessing, catalog, task, artifact, and apply contracts.

### Guardrails Touched

- Current mode: Explore only.
- Durable source mutation: none; wait for explicit user start before changing product code.
- Likely durable owners if implementation starts:
  - `src/xenix/services/ml/models/clustering.py`
  - `src/xenix/services/ml/models/base.py`
  - `src/xenix/services/ml/registry.py`
  - ML registry/execution/Agent harness tests
  - `docs/20-product-tdd/` or `docs/30-unit-tdd/` if capability contracts change

### Current Understanding

- Native clustering currently registers only `clustering.kmeans` and `clustering.dbscan`.
- `UnsupervisedClusteringModelService.fit()` trains a preprocessing + model pipeline, persists cluster assignments, and normalizes DBSCAN-style `-1` noise labels.
- `UnsupervisedClusteringModelService.apply()` currently always raises `ValidationError`, even though the default segmenter result contract exposes apply table output and apply role schema.
- The asset bundle covers:
  - KMeans
  - MiniBatchKMeans
  - Agglomerative
  - DBSCAN
  - OPTICS
  - GaussianMixture
  - SpectralClustering
  - Birch
- Asset `evaluation_with_label.json` results on the simulated labeled customer data:
  - Birch: ARI 0.8011, NMI 0.8430, can_predict true
  - MiniBatchKMeans: ARI 0.7873, NMI 0.8414, can_predict true
  - GaussianMixture: ARI 0.7308, NMI 0.7964, can_predict true
  - KMeans: ARI 0.6492, NMI 0.8163, can_predict true
  - Agglomerative: ARI 0.7270, NMI 0.8656, can_predict false
  - SpectralClustering: ARI 0.6565, NMI 0.8316, can_predict false
  - DBSCAN: ARI 0.0, NMI 0.0, can_predict false
  - OPTICS: ARI -0.0002, NMI 0.0401, can_predict false
- `pdm run python` confirmed sklearn method availability in the project environment:
  - `MiniBatchKMeans`, `Birch`, and `GaussianMixture` have both `fit_predict` and `predict`.
  - `AgglomerativeClustering`, `SpectralClustering`, `DBSCAN`, and `OPTICS` have `fit_predict` but no `predict`.
- Asset docs emphasize that new data should reuse the training-time preprocessing standard rather than refit preprocessing on the new data; native pipelines already align with that direction.
- Asset preprocessing scripts conflict with their own guide in places: one script label-encodes nominal feature columns, while the guide recommends One-Hot for low-cardinality unordered categories. Native `OneHotEncoder(handle_unknown="ignore")` is the safer default.

### Recommendation

- Highest-value usage improvement: implement clustering `apply` for predictable segmenters, appending `cluster_id` to input rows through the persisted pipeline.
- Highest-value model additions:
  - `clustering.minibatch_kmeans`: low-risk extension for larger datasets; same conceptual family as KMeans.
  - `clustering.birch`: strong candidate for scalable segmentation; best ARI in asset evaluation.
  - `clustering.gaussian_mixture`: useful probabilistic clustering option; consider whether to expose probabilities later.
- Defer or gate:
  - Agglomerative and Spectral until the product can honestly represent train-only segmenters or approximate assignment semantics.
  - OPTICS and additional DBSCAN promotion until density-model parameter guidance and no-apply catalog semantics are fixed.
- Existing DBSCAN should be revisited because it is currently cataloged like an apply-capable segmenter even though the estimator cannot predict new rows.

### Verification

- Read asset scripts, configs, evaluation JSON, preprocessing guide, and extracted docx text.
- Read native clustering model, registry, base service, and targeted tests.
- Ran `pdm run python` to verify sklearn predict/fit_predict capability for the candidate estimators.

### Next Step

- If the user explicitly starts implementation, perform an Impact Handshake before source edits.
- Suggested first implementation slice: predictable clusterer apply support plus MiniBatchKMeans and Birch registration.

### Implementation Update

- User explicitly started implementation for:
  - predictable clustering apply support;
  - MiniBatchKMeans;
  - Birch;
  - GaussianMixture.
- Implemented clustering apply in the native base service:
  - loads the persisted sklearn pipeline;
  - validates required apply feature columns;
  - calls `predict` only when the trained estimator exposes it;
  - writes `cluster_predictions.csv`;
  - appends product-facing `cluster_id`.
- Registered new native model services:
  - `clustering.minibatch_kmeans`
  - `clustering.birch`
  - `clustering.gaussian_mixture`
- Left DBSCAN training behavior intact. Runtime apply now fails explicitly for clustering estimators without `predict`, but the broader train-only catalog semantics remain a follow-up concern.

### Implementation Verification

- Passed: `pdm run pytest tests/test_ml_registry.py tests/test_ml_execution.py::test_clustering_fit_runs_without_follow_up_evaluate_and_persists_export_artifact tests/test_ml_execution.py::test_new_predictable_clustering_models_fit_and_persist_export_artifact tests/test_agent_harness_first_slice.py::test_agent_harness_model_metadata_directory_queries_return_lightweight_summaries`
- Passed: `pdm run pytest tests/test_ml_execution.py tests/test_agent_harness_first_slice.py`
- Passed: `pdm run check`
