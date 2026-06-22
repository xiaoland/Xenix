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
