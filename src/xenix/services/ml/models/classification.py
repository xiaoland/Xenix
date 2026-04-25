from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from ...storage.models import ProblemKind
from .base import NumericAndCategoricalModelService


class LogisticRegressionParams(BaseModel):
    c: float = Field(default=1.0, gt=0.0, alias="C", serialization_alias="C")
    max_iter: int = Field(default=2000, ge=100, le=10000)


class LogisticRegressionParamGrid(BaseModel):
    c: list[float] = Field(
        default=[0.01, 0.1, 1.0, 10.0, 100.0],
        min_length=1,
        alias="C",
        serialization_alias="C",
    )
    max_iter: list[int] = Field(default=[2000, 5000, 8000], min_length=1)


class RandomForestClassificationParams(BaseModel):
    n_estimators: int = Field(default=200, ge=10, le=1000)
    max_depth: int | None = Field(default=None, ge=1)
    max_features: Literal["all", "sqrt", "log2"] = Field(default="sqrt")


class RandomForestClassificationParamGrid(BaseModel):
    n_estimators: list[int] = Field(default=[100, 200, 300], min_length=1)
    max_depth: list[int] = Field(default=[0, 5, 10, 15], min_length=1)
    max_features: list[Literal["all", "sqrt", "log2"]] = Field(
        default=["all", "sqrt", "log2"],
        min_length=1,
    )


class DecisionTreeClassificationParams(BaseModel):
    max_depth: int | None = Field(default=None, ge=1)
    min_samples_split: int = Field(default=2, ge=2, le=50)
    min_samples_leaf: int = Field(default=1, ge=1, le=50)
    max_features: Literal["all", "sqrt", "log2"] = Field(default="all")


class DecisionTreeClassificationParamGrid(BaseModel):
    max_depth: list[int] = Field(default=[0, 5, 10, 15], min_length=1)
    min_samples_split: list[int] = Field(default=[2, 5, 10], min_length=1)
    min_samples_leaf: list[int] = Field(default=[1, 2, 4], min_length=1)
    max_features: list[Literal["all", "sqrt", "log2"]] = Field(
        default=["all", "sqrt", "log2"],
        min_length=1,
    )


class GradientBoostingClassificationParams(BaseModel):
    n_estimators: int = Field(default=100, ge=10, le=1000)
    learning_rate: float = Field(default=0.1, gt=0.0, le=1.0)
    max_depth: int = Field(default=3, ge=1, le=20)
    min_samples_split: int = Field(default=2, ge=2, le=50)
    min_samples_leaf: int = Field(default=1, ge=1, le=50)
    subsample: float = Field(default=1.0, gt=0.0, le=1.0)
    max_features: Literal["all", "sqrt", "log2"] = Field(default="all")


class GradientBoostingClassificationParamGrid(BaseModel):
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


class LogisticRegressionService(NumericAndCategoricalModelService):
    key = "classification.logistic_regression"
    display_name = "Logistic Regression"
    problem_kind = ProblemKind.CLASSIFICATION
    params_model = LogisticRegressionParams
    param_grid_model = LogisticRegressionParamGrid
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> LogisticRegression:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("random_state", 42)
        kwargs.setdefault("solver", "lbfgs")
        return LogisticRegression(**kwargs)


class RandomForestClassificationService(NumericAndCategoricalModelService):
    key = "classification.random_forest"
    display_name = "Random Forest Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    params_model = RandomForestClassificationParams
    param_grid_model = RandomForestClassificationParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> RandomForestClassifier:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_depth") == 0:
            kwargs["max_depth"] = None
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        kwargs.setdefault("n_jobs", 1)
        return RandomForestClassifier(**kwargs)


class DecisionTreeClassificationService(NumericAndCategoricalModelService):
    key = "classification.decision_tree"
    display_name = "Decision Tree Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    params_model = DecisionTreeClassificationParams
    param_grid_model = DecisionTreeClassificationParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> DecisionTreeClassifier:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_depth") == 0:
            kwargs["max_depth"] = None
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        return DecisionTreeClassifier(**kwargs)


class GradientBoostingClassificationService(NumericAndCategoricalModelService):
    key = "classification.gradient_boosting"
    display_name = "Gradient Boosting Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    params_model = GradientBoostingClassificationParams
    param_grid_model = GradientBoostingClassificationParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> GradientBoostingClassifier:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        return GradientBoostingClassifier(**kwargs)
