# L2 Plan 03: ML Contracts And Registry

## Pydantic Contract Modules

Add `src/xenix/services/ml/contracts.py` with the core Pydantic models.

### Evaluation policy models

- `ProblemKind(str, Enum)`
  - `REGRESSION`
  - `CLASSIFICATION`
  - `UNSUPERVISED`
- `MetricDirection(str, Enum)`
  - `MAX`
  - `MIN`
- `EvaluationPolicySnapshot(BaseModel)`
  - `policy_key: str`
  - `problem_kind: ProblemKind`
  - `primary_metric_name: str`
  - `primary_metric_direction: MetricDirection`
  - `tie_breaker_metrics: list[str]`
  - `split_strategy: str`
  - `test_size: float`
  - `cv_folds: int | None`
  - `random_state: int`

### Worker request models

- `TaskContinuationPlan(BaseModel)`
  - `next_operation: str`
- `ColumnSelection(BaseModel)`
  - `feature_columns: list[str]`
  - `target_columns: list[str]`
- `ManualTrainingPayload(BaseModel)`
  - `model_key: str`
  - `params: dict[str, Any]`
- `HyperparameterTuningPayload(BaseModel)`
  - `model_key: str`
  - `param_grid: dict[str, list[Any]]`
- `EvaluateModelPayload(BaseModel)`
  - `trained_model_id: str`
  - `model_key: str`
  - `source_ml_task_id: str`
  - `holdout_artifact_relpath: str`
- `MLWorkerTaskRequest(BaseModel)`
  - `task_id: str`
  - `project_id: str`
  - `work_item_id: str`
  - `dataset_id: str`
  - `dataset_source_path: str`
  - `task_type: str`
  - `problem_kind: ProblemKind`
  - `column_selection: ColumnSelection`
  - `evaluation_policy: EvaluationPolicySnapshot`
  - `continuation_plan: TaskContinuationPlan | None`
  - `manual_training: ManualTrainingPayload | None`
  - `hyperparameter_tuning: HyperparameterTuningPayload | None`
  - `evaluate_model: EvaluateModelPayload | None`

### Worker result models

- `CandidateMetrics(BaseModel)`
  - `primary_metric_name: str`
  - `primary_metric_value: float`
  - `metrics: dict[str, float]`
- `TuningSummary(BaseModel)`
  - `best_params: dict[str, Any]`
  - `cv_summary: dict[str, Any]`
- `CandidateResult(BaseModel)`
  - `model_key: str`
  - `params: dict[str, Any]`
  - `metrics: CandidateMetrics`
  - `artifact_relpath: str`
  - `holdout_artifact_relpath: str | None`
  - `tuning_summary: TuningSummary | None`
- `MLWorkerTaskResult(BaseModel)`
  - `task_id: str`
  - `task_type: str`
  - `evaluation_policy: EvaluationPolicySnapshot`
  - `candidate: CandidateResult | None`
  - `evaluation: CandidateMetrics | None`
  - `error_summary: str | None`

## Registry Declaration Style

Use Pydantic-driven declarations with class-level metadata.

Base class shape:

```python
class ModelServiceBase(ABC):
    key: ClassVar[str]
    display_name: ClassVar[str]
    problem_kind: ClassVar[ProblemKind]
    requires_target: ClassVar[bool]
    supports_tuning: ClassVar[bool]
    params_model: ClassVar[type[BaseModel]]
    param_grid_model: ClassVar[type[BaseModel] | None]
```

Concrete services should declare their own metadata directly on the class, so the registry can build `ModelCatalogEntry` objects from those declarations.

## Model Catalog Entry

`ModelCatalogEntry` should be a Pydantic model with:

- `model_key: str`
- `display_name: str`
- `problem_kind: ProblemKind`
- `requires_target: bool`
- `supports_fit: bool`
- `supports_hyperparameter_tuning: bool`
- `param_schema: dict[str, Any]`
- `param_grid_schema: dict[str, Any] | None`

The registry returns `ModelCatalogEntry` to the UI. The UI does not receive Python class references.

## Initial Supported Model Set

Issue `#72` should implement these model services first:

- `regression.linear`
- `regression.ridge`
- `regression.random_forest`
- `classification.logistic_regression`
- `classification.random_forest`

Why this exact set:

- it covers both regression and classification
- it avoids `xgboost` and `lightgbm`
- it stays within scikit-learn and joblib
- it keeps the initial JSON-Schema surface simple

## Evaluation Policy Definitions

Define two initial policies in `src/xenix/services/ml/evaluation.py`.

`regression.default.v1`:

- `primary_metric_name = "r2"`
- `primary_metric_direction = max`
- `tie_breaker_metrics = ["rmse", "mae"]`
- split strategy:
  - holdout test split `0.2`
  - random state `42`
- tuning cross validation:
  - `cv_folds = 5`

`classification.default.v1`:

- `primary_metric_name = "f1_weighted"`
- `primary_metric_direction = max`
- `tie_breaker_metrics = ["accuracy", "precision_weighted", "recall_weighted"]`
- split strategy:
  - stratified holdout `0.2`
  - random state `42`
- tuning cross validation:
  - `cv_folds = 5`

Future unsupervised policies can be added later without changing the public UI contract.

## Worker Algorithms

### Manual training

1. load dataset copy with normalized loader
2. build estimator from validated params
3. derive the train and holdout partitions once within the task
4. fit the model on the training partition
5. save the fitted model to `models/<model_key>.joblib`
6. save the holdout partition as a task-owned artifact for downstream evaluation
7. emit one `CandidateResult`

### Hyperparameter tuning

1. build the estimator from default params
2. run tuning with the validated param grid against the training partition only
3. capture the best params and CV summary
4. fit the best estimator on the training partition
5. save the best fitted model
6. save the holdout partition as a task-owned artifact for downstream evaluation
7. emit one `CandidateResult`

### Evaluation

1. load the persisted model artifact referenced by `trained_model_id`
2. load the holdout artifact produced by the predecessor task
3. evaluate on the held-out partition only
4. emit `CandidateMetrics`

## Dataset Loader Normalization

Add `src/xenix/services/ml/dataset_loader.py` with:

- `load_dataset(path: Path) -> pd.DataFrame`

Behavior:

- `.csv` -> `pandas.read_csv`
- `.xlsx` and `.xls` -> `pandas.read_excel`
- unsupported suffix -> validation error

This hides file-format differences from the model services.

## JSON-Schema Support Envelope

The generic form renderer only needs to support the schema shapes produced by the initial Pydantic models.

Supported patterns in v1:

- primitive `boolean`, `integer`, `number`, `string`
- `enum`
- arrays of primitive values
- optional primitive fields emitted as `anyOf [primitive, null]`
- defaults, descriptions, minimum/maximum constraints

Unsupported patterns in v1:

- deeply nested object trees
- discriminated unions
- arbitrary `oneOf` or `allOf` combinations

The initial model set and param schemas should be kept within this supported envelope.

## Bulk Tuning Delivery Rule

Tuning remains atomic per model.

That means:

- one tuning task request contains one `model_key`
- one tuning task produces one fitted model
- UI multi-select is implemented as repeated task submission, not as a multi-model worker contract
