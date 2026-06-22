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
