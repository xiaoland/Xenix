# Model Migration Guide

Migrate models to use type-safe Pydantic schemas with Generic base classes.

## New Pattern

### 1. Define Pydantic Parameter Schemas

```python
from typing import List, Literal
from pydantic import BaseModel, Field

# Single training parameters
class RidgeParams(BaseModel):
    """Parameters for Ridge Regression"""
    alpha: float = Field(default=1.0, description="Regularization strength")
    solver: Literal["auto", "svd", "cholesky"] = Field(default="auto")
    fit_intercept: bool = Field(default=True)

# GridSearchCV parameter grid
class RidgeParamGrid(BaseModel):
    """Parameter grid for Ridge Regression"""
    alpha: List[float] = Field(default=[0.1, 1.0, 10.0, 100.0])
    solver: List[Literal["auto", "svd", "cholesky"]] = Field(default=["auto", "svd", "cholesky"])
    fit_intercept: List[bool] = Field(default=[True, False])
```

### 2. Update Model Class

```python
from .base import RegressionModel

class RidgeRegression(
    RegressionModel[Ridge, RidgeParams, RidgeParamGrid],
    param_grid=RidgeParamGrid,
    model_param=RidgeParams
):
    """Ridge Regression with L2 regularization"""

    def create_model(self, params: RidgeParams) -> Ridge:
        """Create Ridge model with validated params"""
        return Ridge(**params.model_dump(exclude_none=True))
```

## Benefits

✅ **Type Safety** - Type checkers validate parameter types
✅ **Runtime Validation** - Pydantic validates all parameters
✅ **Auto Documentation** - Schemas include descriptions
✅ **Database Integration** - Generate `model_metadata.json` for migrations
✅ **IDE Support** - Full autocomplete and type hints

## Migration Steps

For each model file (e.g., `lasso.py`, `xgboost.py`):

1. **Define Param Schema** with Pydantic BaseModel
2. **Define ParamGrid Schema** with List fields
3. **Update Class Declaration** to use `RegressionModel[ModelType, ParamType, GridType]`
4. **Add `param_grid` and `model_param` to class declaration**
5. **Replace methods** with single `create_model()` method
6. **Test** the model

## Example Migration

### Before (Old Pattern)

```python
class LassoRegression(RegressionModelBase):
    def get_model_class(self):
        return Lasso

    def get_default_params(self) -> Dict[str, Any]:
        return {"alpha": 1.0}

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "alpha": [0.1, 1.0, 10.0],
            "selection": ["cyclic", "random"]
        }
```

### After (New Pattern)

```python
class LassoParams(BaseModel):
    alpha: float = Field(default=1.0)
    selection: Literal["cyclic", "random"] = Field(default="cyclic")

class LassoParamGrid(BaseModel):
    alpha: List[float] = Field(default=[0.1, 1.0, 10.0])
    selection: List[Literal["cyclic", "random"]] = Field(default=["cyclic", "random"])

class LassoRegression(
    RegressionModel[Lasso, LassoParams, LassoParamGrid],
    param_grid=LassoParamGrid,
    model_param=LassoParams
):
    def create_model(self, params: LassoParams) -> Lasso:
        return Lasso(**params.model_dump(exclude_none=True))
```

## Generate Metadata

After migrating models, generate model_metadata.json:

```bash
python generate_model_metadata.py
```

This creates `model_metadata.json` with schema information for database migration.

## Models to Migrate

- [x] ridge.py ✓ (Example implementation)
- [ ] lasso.py
- [ ] linear.py
- [ ] bayesian_ridge.py
- [ ] polynomial.py
- [ ] knn.py
- [ ] decision_tree.py
- [ ] random_forest.py
- [ ] adaboost.py
- [ ] gbdt.py
- [ ] xgboost.py
- [ ] lightgbm.py
- [ ] classification/logistic_regression.py
- [ ] classification/random_forest.py

## Testing

Test each migrated model:

```bash
echo '{
  "operation": "batch-train",
  "data": {
    "task_id": 123,
    "input_file": "test_data/train.csv",
    "model": "regression.ridge",
    "feature_columns": ["x1", "x2"],
    "target_column": "y",
    "param_grid": {"alpha": [0.1, 1.0]}
  }
}' | python main.py
```
