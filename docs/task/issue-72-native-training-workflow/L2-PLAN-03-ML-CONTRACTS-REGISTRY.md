# L2 Plan 03: ML Contracts And Registry

## Pydantic Contract Modules

Add `src/xenix/services/ml/contracts.py` with the core Pydantic models.

### Dataset inspection models

- `DatasetColumnKind(str, Enum)`
  - `NUMERIC`
  - `BOOLEAN`
  - `CATEGORICAL`
  - `DATETIME`
  - `TEXT`
  - `UNKNOWN`
- `DatasetColumnMetadata(BaseModel)`
  - `name: str`
  - `kind: DatasetColumnKind`
  - `nullable: bool`
- `DatasetInspection(BaseModel)`
  - `dataset_id: str`
  - `source_format: str`
  - `row_count: int`
  - `column_count: int`
  - `columns: list[DatasetColumnMetadata]`

### Evaluation policy models

- `MetricDirection(str, Enum)`
  - `MAX`
  - `MIN`
- `EvaluationPolicySnapshot(BaseModel)`
  - `policy_key: str`
  - `problem_kind: str`
  - `primary_metric_name: str`
  - `primary_metric_direction: MetricDirection`
  - `tie_breaker_metrics: list[str]`
  - `split_strategy: str`
  - `test_size: float`
  - `cv_folds: int | None`
  - `random_state: int`

### Worker request models

- `ColumnSelection(BaseModel)`
  - `feature_columns: list[str]`
  - `target_columns: list[str]`
- `ManualTrainingPayload(BaseModel)`
  - `model_key: str`
  - `params: dict[str, Any]`
- `TuningModelPayload(BaseModel)`
  - `model_key: str`
  - `param_grid: dict[str, list[Any]]`
- `HyperparameterTuningPayload(BaseModel)`
  - `models: list[TuningModelPayload]`
- `MLWorkerTaskRequest(BaseModel)`
  - `task_id: str`
  - `project_id: str`
  - `work_item_id: str`
  - `dataset_id: str`
  - `dataset_source_path: str`
  - `task_type: str`
  - `problem_kind: str`
  - `column_selection: ColumnSelection`
  - `evaluation_policy: EvaluationPolicySnapshot`
  - `manual_training: ManualTrainingPayload | None`
  - `hyperparameter_tuning: HyperparameterTuningPayload | None`

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
  - `problem_kind: str`
  - `params: dict[str, Any]`
  - `metrics: CandidateMetrics`
  - `artifact_relpath: str`
  - `tuning_summary: TuningSummary | None`
  - `is_best_for_task: bool`
- `BestModelDecision(BaseModel)`
  - `winner_model_key: str`
  - `reason: str`
- `MLWorkerTaskResult(BaseModel)`
  - `task_id: str`
  - `task_type: str`
  - `candidates: list[CandidateResult]`
  - `best_model_decision: BestModelDecision`
  - `error_summary: str | None`

## Registry Declaration Style

Use Pydantic-driven declarations with class-level metadata.

Base class shape:

```python
class NativeModelServiceBase(ABC):
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
- `problem_kind: str`
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
- the corresponding code already exists in `../Xenix/packages/ml-backend`
- it avoids `xgboost` and `lightgbm`
- it stays within scikit-learn and joblib

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
3. split into train/test according to the evaluation policy
4. fit the model
5. evaluate the fitted model
6. save the fitted model to `models/<model_key>.joblib`
7. emit one `CandidateResult`

### Hyperparameter tuning

For each selected model:

1. build the estimator from default params
2. run tuning with the validated param grid
3. capture the best params and CV summary
4. run the distinct holdout evaluation step on the best estimator
5. save the best fitted model for that model key
6. emit one `CandidateResult`

After all selected models finish:

7. choose the task winner under the evaluation policy
8. write `BestModelDecision`

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
