from __future__ import annotations

import json

from ..config import AppPaths
from ..exceptions import ValidationError
from .ml.registry import get_model_catalog_entry, list_model_catalog
from .ml.types import ModelCatalogEntry
from .scenario_template_service import (
    ScenarioTemplate,
    ScenarioTemplateService,
    ScenarioTrainingOperation,
    ScenarioTrainingPlanStep,
    build_scenario_training_step_key,
)

_DEFAULTS_FILE_NAME = "scenario_training_defaults.json"


class ScenarioTrainingPresetService:
    def __init__(
        self,
        paths: AppPaths,
        template_service: ScenarioTemplateService,
    ) -> None:
        self._template_service = template_service
        self._defaults_path = paths.config / _DEFAULTS_FILE_NAME

    def list_available_models(self, template_key: str) -> list[ModelCatalogEntry]:
        expected_problem_kind = self._resolve_template_problem_kind(template_key)
        return [
            entry
            for entry in list_model_catalog()
            if entry.problem_kind == expected_problem_kind
        ]

    def load_default_steps(self, template_key: str) -> list[ScenarioTrainingPlanStep]:
        template = self._template_service.get_template(template_key)
        payload = self._read_store().get(template.key)
        if not isinstance(payload, list):
            return self._clone_steps(template.training_plan)

        loaded_steps: list[ScenarioTrainingPlanStep] = []
        seen_model_keys: set[str] = set()
        for raw_step in payload:
            try:
                candidate = ScenarioTrainingPlanStep.model_validate(raw_step)
                loaded_steps.append(
                    self._normalize_step(
                        template=template,
                        step=candidate,
                        seen_model_keys=seen_model_keys,
                    )
                )
            except Exception:
                continue

        if loaded_steps:
            return loaded_steps
        return self._clone_steps(template.training_plan)

    def save_default_steps(self, template_key: str, steps: list[ScenarioTrainingPlanStep]) -> None:
        template = self._template_service.get_template(template_key)
        if not steps:
            raise ValidationError("Select at least one model before saving defaults.")

        normalized_steps: list[ScenarioTrainingPlanStep] = []
        seen_model_keys: set[str] = set()
        for step in steps:
            normalized_steps.append(
                self._normalize_step(
                    template=template,
                    step=step,
                    seen_model_keys=seen_model_keys,
                )
            )

        store = self._read_store()
        store[template.key] = [step.model_dump(mode="json") for step in normalized_steps]
        self._defaults_path.parent.mkdir(parents=True, exist_ok=True)
        self._defaults_path.write_text(
            json.dumps(store, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _resolve_template_problem_kind(self, template_key: str):
        template = self._template_service.get_template(template_key)
        if not template.training_plan:
            raise ValidationError(f"Scenario template '{template.key}' does not define a training plan.")
        return get_model_catalog_entry(template.training_plan[0].model_key).problem_kind

    def _clone_steps(self, steps: list[ScenarioTrainingPlanStep]) -> list[ScenarioTrainingPlanStep]:
        return [ScenarioTrainingPlanStep.model_validate(step.model_dump(mode="json")) for step in steps]

    def _normalize_step(
        self,
        *,
        template: ScenarioTemplate,
        step: ScenarioTrainingPlanStep,
        seen_model_keys: set[str],
    ) -> ScenarioTrainingPlanStep:
        if step.model_key in seen_model_keys:
            raise ValidationError(f"Model '{step.model_key}' is selected more than once.")

        catalog = get_model_catalog_entry(step.model_key)
        expected_problem_kind = self._resolve_template_problem_kind(template.key)
        if catalog.problem_kind != expected_problem_kind:
            raise ValidationError(
                f"Model '{step.model_key}' is incompatible with scenario template '{template.key}'."
            )

        if step.operation is ScenarioTrainingOperation.FIT:
            if not catalog.supports_fit:
                raise ValidationError(f"Model '{step.model_key}' does not support fit training.")
            normalized = ScenarioTrainingPlanStep(
                step_key=step.step_key or build_scenario_training_step_key(step.model_key, step.operation),
                operation=step.operation,
                model_key=step.model_key,
                params=dict(step.params),
                param_grid={},
            )
        else:
            if not catalog.supports_hyperparameter_tuning or catalog.param_grid_schema is None:
                raise ValidationError(f"Model '{step.model_key}' does not support hyperparameter tuning.")
            normalized = ScenarioTrainingPlanStep(
                step_key=step.step_key or build_scenario_training_step_key(step.model_key, step.operation),
                operation=step.operation,
                model_key=step.model_key,
                params={},
                param_grid={key: list(values) for key, values in step.param_grid.items()},
            )

        seen_model_keys.add(step.model_key)
        return normalized

    def _read_store(self) -> dict[str, object]:
        if not self._defaults_path.exists():
            return {}
        try:
            payload = json.loads(self._defaults_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload
