from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field
from sqlmodel import SQLModel

from ..exceptions import NotFoundError


class ScenarioTrainingOperation(StrEnum):
    FIT = "fit"
    HYPERPARAMETER_TUNING = "hyperparameter_tuning"


class ScenarioTrainingPlanStep(SQLModel):
    step_key: str
    operation: ScenarioTrainingOperation
    model_key: str
    params: dict[str, Any] = Field(default_factory=dict)
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


def build_scenario_training_step_key(model_key: str, operation: ScenarioTrainingOperation) -> str:
    normalized_model_key = model_key.replace(".", "_")
    return f"{operation.value}_{normalized_model_key}"


class ScenarioTemplate(SQLModel):
    key: str
    display_name: str
    description: str
    supervised_required: bool
    continues_to_prediction: bool = True
    min_feature_columns: int
    required_target_count: int
    training_plan: list[ScenarioTrainingPlanStep] = Field(default_factory=list)


_TEMPLATES: tuple[ScenarioTemplate, ...] = (
    ScenarioTemplate(
        key="sales_demand_forecast.v1",
        display_name="Sales Demand Forecast",
        description="Forecast numeric business outcomes from a historical dataset.",
        supervised_required=True,
        min_feature_columns=1,
        required_target_count=1,
        training_plan=[
            ScenarioTrainingPlanStep(
                step_key="fit_linear",
                operation=ScenarioTrainingOperation.FIT,
                model_key="regression.linear",
                params={"fit_intercept": True},
            ),
            ScenarioTrainingPlanStep(
                step_key="tune_bayesian_ridge",
                operation=ScenarioTrainingOperation.HYPERPARAMETER_TUNING,
                model_key="regression.bayesian_ridge",
                param_grid={
                    "alpha_1": [0.000001],
                    "alpha_2": [0.000001],
                    "lambda_1": [0.000001, 0.0001],
                    "lambda_2": [0.000001, 0.0001],
                    "max_iter": [300],
                },
            ),
            ScenarioTrainingPlanStep(
                step_key="tune_gradient_boosting",
                operation=ScenarioTrainingOperation.HYPERPARAMETER_TUNING,
                model_key="regression.gradient_boosting",
                param_grid={
                    "n_estimators": [100],
                    "learning_rate": [0.05, 0.1],
                    "max_depth": [2, 3],
                    "min_samples_split": [2],
                    "min_samples_leaf": [1],
                    "subsample": [1.0],
                    "max_features": ["all"],
                },
            ),
        ],
    ),
    ScenarioTemplate(
        key="customer_outcome_classification.v1",
        display_name="Customer Outcome Classification",
        description="Classify a customer outcome such as churn or conversion.",
        supervised_required=True,
        min_feature_columns=1,
        required_target_count=1,
        training_plan=[
            ScenarioTrainingPlanStep(
                step_key="tune_logistic_regression",
                operation=ScenarioTrainingOperation.HYPERPARAMETER_TUNING,
                model_key="classification.logistic_regression",
                param_grid={
                    "C": [0.1, 1.0, 10.0],
                    "max_iter": [2000],
                },
            ),
            ScenarioTrainingPlanStep(
                step_key="tune_naive_bayes",
                operation=ScenarioTrainingOperation.HYPERPARAMETER_TUNING,
                model_key="classification.naive_bayes",
                param_grid={
                    "var_smoothing": [0.0000000001, 0.000000001, 0.00000001],
                },
            ),
            ScenarioTrainingPlanStep(
                step_key="tune_gradient_boosting",
                operation=ScenarioTrainingOperation.HYPERPARAMETER_TUNING,
                model_key="classification.gradient_boosting",
                param_grid={
                    "n_estimators": [50, 100],
                    "learning_rate": [0.05, 0.1],
                    "max_depth": [2, 3],
                    "min_samples_split": [2],
                    "min_samples_leaf": [1],
                    "subsample": [1.0],
                    "max_features": ["all"],
                },
            ),
        ],
    ),
    ScenarioTemplate(
        key="customer_segmentation_clustering.v1",
        display_name="Customer Segmentation Clustering",
        description="Group similar entities into segments from feature-only business data.",
        supervised_required=False,
        continues_to_prediction=False,
        min_feature_columns=1,
        required_target_count=0,
        training_plan=[
            ScenarioTrainingPlanStep(
                step_key="fit_kmeans",
                operation=ScenarioTrainingOperation.FIT,
                model_key="clustering.kmeans",
                params={
                    "n_clusters": 4,
                    "n_init": 10,
                    "max_iter": 300,
                },
            ),
            ScenarioTrainingPlanStep(
                step_key="fit_dbscan",
                operation=ScenarioTrainingOperation.FIT,
                model_key="clustering.dbscan",
                params={
                    "eps": 0.5,
                    "min_samples": 5,
                },
            ),
        ],
    ),
    ScenarioTemplate(
        key="anomaly_detection.v1",
        display_name="Anomaly Detection",
        description="Detect unusual records, rank anomaly severity, and inspect abnormal patterns.",
        supervised_required=False,
        continues_to_prediction=False,
        min_feature_columns=1,
        required_target_count=0,
        training_plan=[
            ScenarioTrainingPlanStep(
                step_key="fit_isolation_forest",
                operation=ScenarioTrainingOperation.FIT,
                model_key="anomaly.isolation_forest",
                params={
                    "n_estimators": 100,
                    "contamination": "auto",
                    "max_samples": "auto",
                },
            ),
            ScenarioTrainingPlanStep(
                step_key="fit_local_outlier_factor",
                operation=ScenarioTrainingOperation.FIT,
                model_key="anomaly.local_outlier_factor",
                params={
                    "n_neighbors": 20,
                    "contamination": "auto",
                    "metric": "minkowski",
                },
            ),
        ],
    ),
    ScenarioTemplate(
        key="key_driver_analysis.v1",
        display_name="Key Driver Analysis",
        description="Rank input columns by their influence on a numeric business target.",
        supervised_required=True,
        continues_to_prediction=False,
        min_feature_columns=1,
        required_target_count=1,
        training_plan=[
            ScenarioTrainingPlanStep(
                step_key="fit_gradient_boosting_drivers",
                operation=ScenarioTrainingOperation.FIT,
                model_key="regression.gradient_boosting",
                params={
                    "n_estimators": 150,
                    "learning_rate": 0.05,
                    "max_depth": 3,
                    "min_samples_split": 2,
                    "min_samples_leaf": 1,
                    "subsample": 1.0,
                    "max_features": "all",
                },
            ),
            ScenarioTrainingPlanStep(
                step_key="fit_lasso_drivers",
                operation=ScenarioTrainingOperation.FIT,
                model_key="regression.lasso",
                params={
                    "alpha": 0.01,
                    "fit_intercept": True,
                },
            ),
        ],
    ),
)


class ScenarioTemplateService:
    def __init__(self) -> None:
        self._templates = {template.key: template for template in _TEMPLATES}

    def list_templates(self) -> list[ScenarioTemplate]:
        return list(self._templates.values())

    def get_template(self, template_key: str) -> ScenarioTemplate:
        template = self._templates.get(template_key)
        if template is None:
            raise NotFoundError(f"Scenario template '{template_key}' was not found.")
        return template
