from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

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
