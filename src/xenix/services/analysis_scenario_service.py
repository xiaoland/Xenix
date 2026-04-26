from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..exceptions import NotFoundError


class AnalysisScenarioAvailability(StrEnum):
    AVAILABLE = "available"
    PLANNED = "planned"


@dataclass(frozen=True)
class AnalysisScenario:
    key: str
    linked_template_keys: tuple[str, ...]
    availability: AnalysisScenarioAvailability


_SCENARIOS: tuple[AnalysisScenario, ...] = (
    AnalysisScenario(
        key="prediction",
        linked_template_keys=("sales_demand_forecast.v1",),
        availability=AnalysisScenarioAvailability.AVAILABLE,
    ),
    AnalysisScenario(
        key="classification",
        linked_template_keys=("customer_outcome_classification.v1",),
        availability=AnalysisScenarioAvailability.AVAILABLE,
    ),
    AnalysisScenario(
        key="clustering",
        linked_template_keys=("customer_segmentation_clustering.v1",),
        availability=AnalysisScenarioAvailability.AVAILABLE,
    ),
    AnalysisScenario(
        key="anomaly_detection",
        linked_template_keys=("anomaly_detection.v1",),
        availability=AnalysisScenarioAvailability.AVAILABLE,
    ),
    AnalysisScenario(
        key="key_driver_analysis",
        linked_template_keys=("key_driver_analysis.v1",),
        availability=AnalysisScenarioAvailability.AVAILABLE,
    ),
)


class AnalysisScenarioService:
    def __init__(self) -> None:
        self._scenarios = {scenario.key: scenario for scenario in _SCENARIOS}

    def list_scenarios(self) -> list[AnalysisScenario]:
        return list(self._scenarios.values())

    def get_scenario(self, scenario_key: str) -> AnalysisScenario:
        scenario = self._scenarios.get(scenario_key)
        if scenario is None:
            raise NotFoundError(f"Analysis scenario '{scenario_key}' was not found.")
        return scenario
