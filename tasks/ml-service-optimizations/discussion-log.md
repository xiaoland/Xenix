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
