from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from sklearn.ensemble import AdaBoostRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import BayesianRidge, Lasso, LinearRegression, Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures
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


class BayesianRidgeParams(BaseModel):
    alpha_1: float = Field(default=1e-6, gt=0.0, description="Gamma prior shape for alpha.")
    alpha_2: float = Field(default=1e-6, gt=0.0, description="Gamma prior inverse scale for alpha.")
    lambda_1: float = Field(default=1e-6, gt=0.0, description="Gamma prior shape for lambda.")
    lambda_2: float = Field(default=1e-6, gt=0.0, description="Gamma prior inverse scale for lambda.")
    max_iter: int = Field(default=300, ge=10, le=10000)


class BayesianRidgeParamGrid(BaseModel):
    alpha_1: list[float] = Field(default=[1e-6, 1e-4], min_length=1)
    alpha_2: list[float] = Field(default=[1e-6, 1e-4], min_length=1)
    lambda_1: list[float] = Field(default=[1e-6, 1e-4], min_length=1)
    lambda_2: list[float] = Field(default=[1e-6, 1e-4], min_length=1)
    max_iter: list[int] = Field(default=[300], min_length=1)


class KNeighborsRegressionParams(BaseModel):
    n_neighbors: int = Field(default=5, ge=1, le=100)
    weights: Literal["uniform", "distance"] = Field(default="uniform")
    p: Literal[1, 2] = Field(default=2)


class KNeighborsRegressionParamGrid(BaseModel):
    n_neighbors: list[int] = Field(default=[3, 5, 7], min_length=1)
    weights: list[Literal["uniform", "distance"]] = Field(default=["uniform", "distance"], min_length=1)
    p: list[Literal[1, 2]] = Field(default=[1, 2], min_length=1)


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


class AdaBoostRegressionParams(BaseModel):
    n_estimators: int = Field(default=100, ge=10, le=1000)
    learning_rate: float = Field(default=0.1, gt=0.0, le=2.0)
    loss: Literal["linear", "square", "exponential"] = Field(default="linear")
    estimator_max_depth: int = Field(default=3, ge=1, le=20)


class AdaBoostRegressionParamGrid(BaseModel):
    n_estimators: list[int] = Field(default=[50, 100, 200], min_length=1)
    learning_rate: list[float] = Field(default=[0.01, 0.1, 0.5], min_length=1)
    loss: list[Literal["linear", "square", "exponential"]] = Field(
        default=["linear", "square", "exponential"],
        min_length=1,
    )
    estimator_max_depth: list[int] = Field(default=[2, 3, 4], min_length=1)


class PolynomialRegressionParams(BaseModel):
    degree: int = Field(default=2, ge=1, le=4)
    fit_intercept: bool = Field(default=True, description="Whether to calculate the intercept.")


class PolynomialRegressionParamGrid(BaseModel):
    degree: list[int] = Field(default=[1, 2, 3], min_length=1)
    fit_intercept: list[bool] = Field(default=[True, False], min_length=1)


class LinearRegressionService(NumericAndCategoricalModelService):
    key = "regression.linear"
    display_name = "Linear Regression"
    problem_kind = ProblemKind.REGRESSION
    family = "Linear baseline"
    guidance = "Fast baseline for mostly linear numeric relationships."
    recommendation_tier = 10
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
    family = "Regularized linear"
    guidance = "Shrinks weaker signals and can make wide feature sets easier to interpret."
    recommendation_tier = 30
    params_model = LassoParams
    param_grid_model = LassoParamGrid
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> Lasso:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("max_iter", 5000)
        return Lasso(**kwargs)


class BayesianRidgeRegressionService(NumericAndCategoricalModelService):
    key = "regression.bayesian_ridge"
    display_name = "Bayesian Ridge Regression"
    problem_kind = ProblemKind.REGRESSION
    family = "Regularized linear"
    guidance = "Stable regularized linear model for smaller datasets or correlated inputs."
    recommendation_tier = 15
    params_model = BayesianRidgeParams
    param_grid_model = BayesianRidgeParamGrid
    scaler_for_numeric = True
    dense_preprocessing = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> BayesianRidge:
        return BayesianRidge(**estimator_kwargs)


class RidgeRegressionService(NumericAndCategoricalModelService):
    key = "regression.ridge"
    display_name = "Ridge Regression"
    problem_kind = ProblemKind.REGRESSION
    family = "Regularized linear"
    guidance = "Stabilizes linear regression when input columns move together."
    recommendation_tier = 20
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
    family = "Tree ensemble"
    guidance = "Robust nonlinear benchmark for mixed business tables."
    recommendation_tier = 35
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


class KNeighborsRegressionService(NumericAndCategoricalModelService):
    key = "regression.knn"
    display_name = "K-Nearest Neighbors Regressor"
    problem_kind = ProblemKind.REGRESSION
    family = "Similarity based"
    guidance = "Predicts from nearby rows; works best when numeric inputs share comparable scale."
    recommendation_tier = 60
    params_model = KNeighborsRegressionParams
    param_grid_model = KNeighborsRegressionParamGrid
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> KNeighborsRegressor:
        return KNeighborsRegressor(**estimator_kwargs)


class DecisionTreeRegressionService(NumericAndCategoricalModelService):
    key = "regression.decision_tree"
    display_name = "Decision Tree Regressor"
    problem_kind = ProblemKind.REGRESSION
    family = "Tree model"
    guidance = "Explainable nonlinear baseline that can overfit small datasets."
    recommendation_tier = 50
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
    family = "Boosted trees"
    guidance = "Strong nonlinear candidate for tabular demand and value prediction."
    recommendation_tier = 25
    params_model = GradientBoostingRegressionParams
    param_grid_model = GradientBoostingRegressionParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> GradientBoostingRegressor:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        return GradientBoostingRegressor(**kwargs)


class AdaBoostRegressionService(NumericAndCategoricalModelService):
    key = "regression.ada_boost"
    display_name = "AdaBoost Regressor"
    problem_kind = ProblemKind.REGRESSION
    family = "Boosted trees"
    guidance = "Builds a sequence of small trees to improve difficult rows."
    recommendation_tier = 45
    params_model = AdaBoostRegressionParams
    param_grid_model = AdaBoostRegressionParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> AdaBoostRegressor:
        kwargs = dict(estimator_kwargs)
        estimator_max_depth = int(kwargs.pop("estimator_max_depth", 3))
        kwargs.setdefault(
            "estimator",
            DecisionTreeRegressor(max_depth=estimator_max_depth, random_state=42),
        )
        kwargs.setdefault("random_state", 42)
        return AdaBoostRegressor(**kwargs)

    @classmethod
    def _build_param_grid(cls, param_grid_model: BaseModel) -> dict[str, list[Any]]:
        payload = param_grid_model.model_dump(mode="json", by_alias=True)
        grid: dict[str, list[Any]] = {}
        for key, values in payload.items():
            if key == "estimator_max_depth":
                grid["model__estimator__max_depth"] = list(values)
            else:
                grid[f"model__{key}"] = list(values)
        return grid


class PolynomialRegressionService(NumericAndCategoricalModelService):
    key = "regression.polynomial"
    display_name = "Polynomial Regression"
    problem_kind = ProblemKind.REGRESSION
    family = "Feature expansion"
    guidance = "Captures curved numeric relationships when a simple line underfits."
    recommendation_tier = 70
    params_model = PolynomialRegressionParams
    param_grid_model = PolynomialRegressionParamGrid
    scaler_for_numeric = True
    dense_preprocessing = True

    @classmethod
    def _build_pipeline(cls, **estimator_kwargs: Any) -> Pipeline:
        degree = int(estimator_kwargs.pop("degree", 2))
        fit_intercept = bool(estimator_kwargs.pop("fit_intercept", True))
        return Pipeline(
            steps=[
                ("preprocess", cls._build_preprocessor()),
                ("polynomial", PolynomialFeatures(degree=degree, include_bias=False)),
                ("model", LinearRegression(fit_intercept=fit_intercept)),
            ]
        )

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> LinearRegression:
        return LinearRegression(**estimator_kwargs)

    @classmethod
    def _build_param_grid(cls, param_grid_model: BaseModel) -> dict[str, list[Any]]:
        payload = param_grid_model.model_dump(mode="json", by_alias=True)
        grid: dict[str, list[Any]] = {}
        if "degree" in payload:
            grid["polynomial__degree"] = list(payload["degree"])
        if "fit_intercept" in payload:
            grid["model__fit_intercept"] = list(payload["fit_intercept"])
        return grid
