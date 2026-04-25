from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from ..services.scenario_template_service import ScenarioTemplate


def localized_template_display_name(template: ScenarioTemplate) -> str:
    if template.key == "sales_demand_forecast.v1":
        return QCoreApplication.translate("ScenarioTemplateText", "Sales Demand Forecast")
    if template.key == "customer_outcome_classification.v1":
        return QCoreApplication.translate("ScenarioTemplateText", "Customer Outcome Classification")
    if template.key == "customer_segmentation_clustering.v1":
        return QCoreApplication.translate("ScenarioTemplateText", "Customer Segmentation Clustering")
    return template.display_name


def localized_template_description(template: ScenarioTemplate) -> str:
    if template.key == "sales_demand_forecast.v1":
        return QCoreApplication.translate(
            "ScenarioTemplateText",
            "Forecast numeric business outcomes from a historical dataset.",
        )
    if template.key == "customer_outcome_classification.v1":
        return QCoreApplication.translate(
            "ScenarioTemplateText",
            "Classify a customer outcome such as churn or conversion.",
        )
    if template.key == "customer_segmentation_clustering.v1":
        return QCoreApplication.translate(
            "ScenarioTemplateText",
            "Group similar entities into segments from feature-only business data.",
        )
    return template.description
