from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from ..services.analysis_scenario_service import AnalysisScenario, AnalysisScenarioAvailability


def localized_analysis_scenario_display_name(scenario: AnalysisScenario) -> str:
    if scenario.key == "prediction":
        return QCoreApplication.translate("AnalysisScenarioText", "Prediction")
    if scenario.key == "classification":
        return QCoreApplication.translate("AnalysisScenarioText", "Classification")
    if scenario.key == "clustering":
        return QCoreApplication.translate("AnalysisScenarioText", "Clustering")
    if scenario.key == "anomaly_detection":
        return QCoreApplication.translate("AnalysisScenarioText", "Anomaly Detection")
    if scenario.key == "key_driver_analysis":
        return QCoreApplication.translate("AnalysisScenarioText", "Key Driver Analysis")
    return scenario.key


def localized_analysis_scenario_description(scenario: AnalysisScenario) -> str:
    if scenario.key == "prediction":
        return QCoreApplication.translate(
            "AnalysisScenarioText",
            "Prepare a historical dataset, train forecasting models, and predict numeric business outcomes.",
        )
    if scenario.key == "classification":
        return QCoreApplication.translate(
            "AnalysisScenarioText",
            "Prepare labeled data, train classification models, and predict discrete business outcomes.",
        )
    if scenario.key == "clustering":
        return QCoreApplication.translate(
            "AnalysisScenarioText",
            "Group similar entities into segments and compare segment-level characteristics.",
        )
    if scenario.key == "anomaly_detection":
        return QCoreApplication.translate(
            "AnalysisScenarioText",
            "Detect unusual records, rank anomaly severity, and inspect abnormal patterns.",
        )
    if scenario.key == "key_driver_analysis":
        return QCoreApplication.translate(
            "AnalysisScenarioText",
            "Rank business drivers, inspect impact direction, and explain influential factors.",
        )
    return scenario.key


def localized_analysis_scenario_status(scenario: AnalysisScenario) -> str:
    if scenario.availability is AnalysisScenarioAvailability.AVAILABLE:
        return QCoreApplication.translate("AnalysisScenarioText", "Available Now")
    return QCoreApplication.translate("AnalysisScenarioText", "Planned")
