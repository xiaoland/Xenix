# L3 Plan 03: Registry, Evaluation, And Model Adapters

## Step 1: Replace The Placeholder Registry

Files:

- `src/xenix/services/ml/registry.py`
- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/contracts.py`

Current baseline:

- `registry.py` is effectively empty
- `types.py` only exposes a minimal `ModelDefinition`

Target:

- registry entries are project-owned declarations under `src/xenix/services/ml/`
- schemas are exported from Pydantic models
- the UI only receives serializable catalog entries

## Registry Shape

Implementation approach:

1. define a base model-service class with class-level metadata
2. define `ModelCatalogEntry` as a Pydantic response model
3. register concrete model services in one module-level registry
4. export `param_schema` and `param_grid_schema` through `model_json_schema()`

Pseudo-code:

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

## Step 2: Add Model-Service Modules

Files:

- `src/xenix/services/ml/models/base.py`
- `src/xenix/services/ml/models/regression.py`
- `src/xenix/services/ml/models/classification.py`
- `src/xenix/services/ml/dataset_loader.py`
- `src/xenix/services/ml/evaluation.py`

Initial model set:

- `regression.linear`
- `regression.ridge`
- `regression.random_forest`
- `classification.logistic_regression`
- `classification.random_forest`

Ownership rule:

- use `ml/` as behavior reference only
- model services should instantiate and evaluate estimators in `src/xenix/services/ml/...`
- do not import or mutate the legacy `ml/` scripts directly

## Parameter And Grid Models

Each model service needs:

- one `Params` Pydantic model for manual training
- one `ParamGrid` Pydantic model when tuning is supported
- defaults that keep generated JSON Schema simple enough for the generic form widget

Practical constraint:

- avoid nested object graphs or discriminated unions in the initial schemas
- keep array values primitive and serializable

## Step 3: Define Evaluation Policies Once

Files:

- `src/xenix/services/ml/evaluation.py`

Required outputs:

- `regression.default.v1`
- `classification.default.v1`
- helper to compare two evaluation snapshots under one policy
- helper to evaluate a persisted holdout artifact under one policy

Pseudo-code:

```python
def choose_better_candidate(policy, left, right):
    if left.primary_metric_value != right.primary_metric_value:
        return higher_or_lower_by_direction(...)
    return compare_tie_breakers(...)
```

Metric rules:

- regression primary metric: `r2`
- classification primary metric: `f1_weighted`

The comparison helper should be reused by:

- worker result evaluation
- `best_trained_model_id` replacement logic

## Step 4: Standardize Dataset Loading And Splits

Files:

- `src/xenix/services/ml/dataset_loader.py`
- `src/xenix/services/ml/models/*.py`

Dataset loader responsibilities:

- normalize `.csv`, `.xlsx`, and `.xls`
- return one dataframe API to every model service

Model service responsibilities:

- build feature matrix and target array from persisted work-item selection
- consume task-owned training or holdout artifacts instead of reaching back into live external dataset state during evaluation
- produce serializable metric dictionaries
- persist fitted estimators with `joblib`

## Step 5: Add Narrow Tests Around Registry And Model Helpers

Tests:

- `tests/test_ml_registry.py`
- `tests/test_ml_models.py`

Coverage:

- catalog export includes JSON Schema
- invalid model lookup fails clearly
- parameter validation surfaces Pydantic errors cleanly
- regression and classification helpers emit metrics in the expected shape
- predecessor-task holdout artifacts avoid fit/evaluate partition drift
- the worker evaluation snapshot uses the same policy helper as best-model updates
