from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from sklearn.ensemble import AdaBoostClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
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


class NaiveBayesClassificationParams(BaseModel):
    var_smoothing: float = Field(default=1e-9, gt=0.0)


class NaiveBayesClassificationParamGrid(BaseModel):
    var_smoothing: list[float] = Field(default=[1e-12, 1e-10, 1e-9, 1e-8, 1e-6], min_length=1)


class KNeighborsClassificationParams(BaseModel):
    n_neighbors: int = Field(default=5, ge=1, le=100)
    weights: Literal["uniform", "distance"] = Field(default="uniform")
    p: Literal[1, 2] = Field(default=2)


class KNeighborsClassificationParamGrid(BaseModel):
    n_neighbors: list[int] = Field(default=[3, 5, 7], min_length=1)
    weights: list[Literal["uniform", "distance"]] = Field(default=["uniform", "distance"], min_length=1)
    p: list[Literal[1, 2]] = Field(default=[1, 2], min_length=1)


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


class AdaBoostClassificationParams(BaseModel):
    n_estimators: int = Field(default=100, ge=10, le=1000)
    learning_rate: float = Field(default=0.1, gt=0.0, le=2.0)
    estimator_max_depth: int = Field(default=1, ge=1, le=20)


class AdaBoostClassificationParamGrid(BaseModel):
    n_estimators: list[int] = Field(default=[50, 100, 200], min_length=1)
    learning_rate: list[float] = Field(default=[0.01, 0.1, 0.5, 1.0], min_length=1)
    estimator_max_depth: list[int] = Field(default=[1, 2, 3], min_length=1)


class LogisticRegressionService(NumericAndCategoricalModelService):
    key = "classification.logistic_regression"
    display_name = "Logistic Regression"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Linear baseline"
    guidance = "Fast baseline for customer outcome classification with clear probability scores."
    recommendation_tier = 10
    params_model = LogisticRegressionParams
    param_grid_model = LogisticRegressionParamGrid
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> LogisticRegression:
        kwargs = dict(estimator_kwargs)
        kwargs.setdefault("random_state", 42)
        kwargs.setdefault("solver", "lbfgs")
        return LogisticRegression(**kwargs)


class NaiveBayesClassificationService(NumericAndCategoricalModelService):
    key = "classification.naive_bayes"
    display_name = "Naive Bayes Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Probabilistic baseline"
    guidance = "Simple probabilistic model that is useful as a quick classification benchmark."
    recommendation_tier = 20
    params_model = NaiveBayesClassificationParams
    param_grid_model = NaiveBayesClassificationParamGrid
    scaler_for_numeric = True
    dense_preprocessing = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> GaussianNB:
        return GaussianNB(**estimator_kwargs)


class RandomForestClassificationService(NumericAndCategoricalModelService):
    key = "classification.random_forest"
    display_name = "Random Forest Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Tree ensemble"
    guidance = "Robust nonlinear benchmark for mixed customer and operations data."
    recommendation_tier = 35
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


class KNeighborsClassificationService(NumericAndCategoricalModelService):
    key = "classification.knn"
    display_name = "K-Nearest Neighbors Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Similarity based"
    guidance = "Classifies by nearby examples; works best when similar rows should share outcomes."
    recommendation_tier = 60
    params_model = KNeighborsClassificationParams
    param_grid_model = KNeighborsClassificationParamGrid
    scaler_for_numeric = True

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> KNeighborsClassifier:
        return KNeighborsClassifier(**estimator_kwargs)


class DecisionTreeClassificationService(NumericAndCategoricalModelService):
    key = "classification.decision_tree"
    display_name = "Decision Tree Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Tree model"
    guidance = "Explainable nonlinear baseline for simple branching business rules."
    recommendation_tier = 50
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
    family = "Boosted trees"
    guidance = "Strong nonlinear candidate for churn, conversion, and other tabular outcomes."
    recommendation_tier = 25
    params_model = GradientBoostingClassificationParams
    param_grid_model = GradientBoostingClassificationParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> GradientBoostingClassifier:
        kwargs = dict(estimator_kwargs)
        if kwargs.get("max_features") == "all":
            kwargs["max_features"] = 1.0
        kwargs.setdefault("random_state", 42)
        return GradientBoostingClassifier(**kwargs)


class AdaBoostClassificationService(NumericAndCategoricalModelService):
    key = "classification.ada_boost"
    display_name = "AdaBoost Classifier"
    problem_kind = ProblemKind.CLASSIFICATION
    family = "Boosted trees"
    guidance = "Combines small trees to focus on rows previous trees misclassified."
    recommendation_tier = 45
    params_model = AdaBoostClassificationParams
    param_grid_model = AdaBoostClassificationParamGrid

    @classmethod
    def _build_estimator(cls, **estimator_kwargs: object) -> AdaBoostClassifier:
        kwargs = dict(estimator_kwargs)
        estimator_max_depth = int(kwargs.pop("estimator_max_depth", 1))
        kwargs.setdefault(
            "estimator",
            DecisionTreeClassifier(max_depth=estimator_max_depth, random_state=42),
        )
        kwargs.setdefault("random_state", 42)
        return AdaBoostClassifier(**kwargs)

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
