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
    if template.key == "anomaly_detection.v1":
        return QCoreApplication.translate("ScenarioTemplateText", "Anomaly Detection")
    if template.key == "key_driver_analysis.v1":
        return QCoreApplication.translate("ScenarioTemplateText", "Key Driver Analysis")
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
    if template.key == "anomaly_detection.v1":
        return QCoreApplication.translate(
            "ScenarioTemplateText",
            "Detect unusual records, rank anomaly severity, and inspect abnormal patterns.",
        )
    if template.key == "key_driver_analysis.v1":
        return QCoreApplication.translate(
            "ScenarioTemplateText",
            "Rank input columns by their influence on a numeric business target.",
        )
    return template.description
