from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.tree import DecisionTreeRegressor

from ...storage.models import ProblemKind
from .base import BooleanGridModel, NumericAndCategoricalModelService


class LinearRegressionParams(BaseModel):
    fit_intercept: bool = Field(default=True, description="Whether to calculate the intercept.")


class RidgeParams(BaseModel):
    alpha: float = Field(default=1.0, ge=0.0001, description="L2 regularization strength.")
    fit_intercept: bool = Field(default=True, description="Whether to calculate the intercept.")


class RidgeParamGrid(BaseModel):
    alpha: list[float] = Field(
        default=[0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0],
        min_length=1,
        description="Candidate alpha values.",
    )
    fit_intercept: list[bool] = Field(
        default=[True, False],
        min_length=1,
        description="Candidate fit_intercept values.",
    )


class LassoParams(BaseModel):
    alpha: float = Field(default=1.0, ge=0.0001, description="L1 regularization strength.")
    fit_intercept: bool = Field(default=True, description="Whether to calculate the intercept.")


class LassoParamGrid(BaseModel):
    alpha: list[float] = Field(
        default=[0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0],
        min_length=1,
        description="Candidate alpha values.",
    )
    fit_intercept: list[bool] = Field(
        default=[True, False],
        min_length=1,
        description="Candidate fit_intercept values.",
    )


class RandomForestRegressionParams(BaseModel):
    n_estimators: int = Field(default=200, ge=10, le=1000)
    max_depth: int | None = Field(default=None, ge=1)
    min_samples_split: int = Field(default=2, ge=2, le=50)
    min_samples_leaf: int = Field(default=1, ge=1, le=50)
    max_features: Literal["all", "sqrt", "log2"] = Field(default="sqrt")


class RandomForestRegressionParamGrid(BaseModel):
    n_estimators: list[int] = Field(default=[100, 200, 300], min_length=1)
    max_depth: list[int] = Field(default=[0, 5, 10, 15], min_length=1)
    min_samples_split: list[int] = Field(default=[2, 5, 10], min_length=1)
    min_samples_leaf: list[int] = Field(default=[1, 2, 4], min_length=1)
    max_features: list[Literal["all", "sqrt", "log2"]] = Field(
        default=["all", "sqrt", "log2"],
        min_length=1,
    )


class DecisionTreeRegressionParams(BaseModel):
    max_depth: int | None = Field(default=None, ge=1)
    min_samples_split: int = Field(default=2, ge=2, le=50)
    min_samples_leaf: int = Field(default=1, ge=1, le=50)
    max_features: Literal["all", "sqrt", "log2"] = Field(default="all")


class DecisionTreeRegressionParamGrid(BaseModel):
    max_depth: list[int] = Field(default=[0, 5, 10, 15], min_length=1)
    min_samples_split: list[int] = Field(default=[2, 5, 10], min_length=1)
    min_samples_leaf: list[int] = Field(default=[1, 2, 4], min_length=1)
    max_features: list[Literal["all", "sqrt", "log2"]] = Field(
        default=["all", "sqrt", "log2"],
        min_length=1,
    )


class GradientBoostingRegressionParams(BaseModel):
    n_estimators: int = Field(default=100, ge=10, le=1000)
    learning_rate: float = Field(default=0.1, gt=0.0, le=1.0)
    max_depth: int = Field(default=3, ge=1, le=20)
    min_samples_split: int = Field(default=2, ge=2, le=50)
    min_samples_leaf: int = Field(default=1, ge=1, le=50)
    subsample: float = Field(default=1.0, gt=0.0, le=1.0)
    max_features: Literal["all", "sqrt", "log2"] = Field(default="all")


class GradientBoostingRegressionParamGrid(BaseModel):
    n_estimators: list[int] = Field(default=[50, 100, 200], min_length=1)
    learning_rate: list[float] = Field(default=[0.01, 0.05, 0.1, 0.2], min_length=1)
    max_depth: list[int] = Field(default=[2, 3, 5], min_length=1)
    min_samples_split: list[int] = Field(default=[2, 5, 10], min_length=1)
    min_samples_leaf: list[int] = Field(default=[1, 2, 4], min_length=1)
    subsample: list[float] = Field(default=[0.8, 1.0], min_length=1)
    max_features: list[Literal["all", "sqrt", "log2"]] = Field(
        default=["all", "sqrt", "log2"],
        min_length=1,
    )


class LinearRegressionService(NumericAndCategoricalModelService):
    key = "regression.linear"
    display_name = "Linear Regression"
    problem_kind = ProblemKind.REGRESSION
    params_model = LinearRegressionParams
    param_grid_model = BooleanGridModel
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> LinearRegression:
        return LinearRegression(**estimator_kwargs)


class LassoRegressionService(NumericAndCategoricalModelService):
    key = "regression.lasso"
    display_name = "Lasso Regression"
    problem_kind = ProblemKind.REGRESSION
    params_model = LassoParams
    param_grid_model = LassoParamGrid
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> Lasso:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("max_iter", 5000)
        return Lasso(**kwargs)


class RidgeRegressionService(NumericAndCategoricalModelService):
    key = "regression.ridge"
    display_name = "Ridge Regression"
    problem_kind = ProblemKind.REGRESSION
    params_model = RidgeParams
    param_grid_model = RidgeParamGrid
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> Ridge:
        return Ridge(**estimator_kwargs)


class RandomForestRegressionService(NumericAndCategoricalModelService):
    key = "regression.random_forest"
    display_name = "Random Forest Regressor"
    problem_kind = ProblemKind.REGRESSION
    params_model = RandomForestRegressionParams
    param_grid_model = RandomForestRegressionParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> RandomForestRegressor:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_depth") == 0:
            kwargs["max_depth"] = None
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        kwargs.setdefault("n_jobs", 1)
        return RandomForestRegressor(**kwargs)


class DecisionTreeRegressionService(NumericAndCategoricalModelService):
    key = "regression.decision_tree"
    display_name = "Decision Tree Regressor"
    problem_kind = ProblemKind.REGRESSION
    params_model = DecisionTreeRegressionParams
    param_grid_model = DecisionTreeRegressionParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> DecisionTreeRegressor:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_depth") == 0:
            kwargs["max_depth"] = None
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        return DecisionTreeRegressor(**kwargs)


class GradientBoostingRegressionService(NumericAndCategoricalModelService):
    key = "regression.gradient_boosting"
    display_name = "Gradient Boosting Regressor"
    problem_kind = ProblemKind.REGRESSION
    params_model = GradientBoostingRegressionParams
    param_grid_model = GradientBoostingRegressionParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> GradientBoostingRegressor:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        return GradientBoostingRegressor(**kwargs)
