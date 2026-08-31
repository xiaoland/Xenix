from __future__ import annotations

from typing import Any

from ...exceptions import ValidationError
from ..ml.registry import get_model_catalog_entry, list_model_catalog, list_model_keys
from ..ml.types import EvaluationKind, ModelCatalogEntry, ModelTaskKind


_MODEL_ALIAS_SUFFIXES = {
    "classification",
    "classifier",
    "clustering",
    "regression",
    "regressor",
}
_MODEL_KEY_ALIAS_OVERRIDES = {
    "k_neighbors": "regression.knn",
    "kneighbors": "regression.knn",
    "k_neighbors_classifier": "classification.knn",
    "kneighborsclassifier": "classification.knn",
    "k_neighbors_regressor": "regression.knn",
    "kneighborsregressor": "regression.knn",
}


class _ModelKeyMixin:
    def _model_catalog_payload(
        self,
        entry: ModelCatalogEntry,
        *,
        detail_query: bool,
        include_param_schema: bool,
        include_param_grid_schema: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model_key": entry.model_key,
            "display_name": entry.display_name,
            "description": entry.guidance,
            "problem_kind": entry.problem_kind.value if entry.problem_kind is not None else None,
            "evaluation_kind": entry.evaluation_kind.value,
            "model_family": entry.model_family.value,
            "model_task_kind": entry.model_task_kind.value,
            "family": entry.family,
            "recommendation_tier": entry.recommendation_tier,
            "supports_fit": entry.supports_fit,
            "supports_evaluation": entry.supports_evaluation,
            "supports_apply": entry.supports_apply,
            "apply_mode": entry.apply_mode.value,
            "supports_hyperparameter_tuning": entry.supports_hyperparameter_tuning,
        }
        if detail_query:
            payload.update(
                {
                    "summary_metric_name": entry.summary_metric_name,
                    "requires_target": entry.requires_target,
                    "train_role_schema": entry.train_role_schema.model_dump(mode="json"),
                    "apply_role_schema": entry.apply_role_schema.model_dump(mode="json"),
                    "result_contract": entry.result_contract.model_dump(mode="json"),
                }
            )
        if include_param_schema:
            payload["param_schema"] = entry.param_schema
        if include_param_grid_schema:
            payload["param_grid_schema"] = entry.param_grid_schema
        return payload

    def _normalize_model_mapping(
        self,
        raw_mapping: Any,
        *,
        field_name: str,
        require_hyperparameter_tuning: bool = False,
    ) -> dict[str, Any]:
        if raw_mapping is None:
            return {}
        if not isinstance(raw_mapping, dict):
            raise ValidationError(f"{field_name} must be an object keyed by model key.")
        normalized: dict[str, Any] = {}
        failures: list[str] = []
        for raw_key, value in raw_mapping.items():
            model_key = self._canonical_model_key(str(raw_key))
            if model_key is None:
                failures.append(str(raw_key))
                continue
            if value is None:
                value = {}
            if not isinstance(value, dict):
                failures.append(f"{raw_key} must map to an object")
                continue
            if require_hyperparameter_tuning:
                catalog = get_model_catalog_entry(model_key)
                if not catalog.supports_hyperparameter_tuning:
                    failures.append(f"{raw_key} lacks hyperparameter_tuning support")
                    continue
            normalized[model_key] = value
        if failures:
            raise ValidationError(self._model_key_error_message(field_name, failures))
        return normalized

    def _normalize_model_keys(
        self,
        raw_keys: list[str],
        *,
        field_name: str,
        require_hyperparameter_tuning: bool = False,
    ) -> list[str]:
        normalized: list[str] = []
        failures: list[str] = []
        for raw_key in raw_keys:
            model_key = self._canonical_model_key(raw_key)
            if model_key is None:
                failures.append(raw_key)
                continue
            if require_hyperparameter_tuning:
                catalog = get_model_catalog_entry(model_key)
                if not catalog.supports_hyperparameter_tuning:
                    failures.append(f"{raw_key} lacks hyperparameter_tuning support")
                    continue
            if model_key not in normalized:
                normalized.append(model_key)
        if failures:
            raise ValidationError(self._model_key_error_message(field_name, failures))
        return normalized

    def _canonical_model_key(self, raw_key: str) -> str | None:
        value = raw_key.strip()
        available = set(list_model_keys())
        if value in available:
            return value
        lowered = value.lower()
        if lowered in available:
            return lowered
        for token in self._model_key_alias_tokens(value):
            aliased = self._model_key_aliases.get(token)
            if aliased in available:
                return aliased
        return None

    def _build_model_key_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        priorities: dict[str, int] = {}
        for entry in list_model_catalog():
            priority = self._model_alias_priority(entry)
            for token in self._model_entry_alias_tokens(entry):
                if priority < priorities.get(token, 100):
                    aliases[token] = entry.model_key
                    priorities[token] = priority
        aliases.update(_MODEL_KEY_ALIAS_OVERRIDES)
        return aliases

    def _model_entry_alias_tokens(self, entry: ModelCatalogEntry) -> set[str]:
        leaf_key = entry.model_key.split(".", 1)[-1]
        values = {
            entry.model_key,
            entry.model_key.replace(".", "_"),
            leaf_key,
            entry.display_name,
            f"{entry.evaluation_kind.value}_{leaf_key}",
            f"{entry.model_family.value}_{leaf_key}",
            f"{entry.model_task_kind.value}_{leaf_key}",
        }
        if entry.problem_kind is not None:
            values.add(f"{entry.problem_kind.value}_{leaf_key}")
        tokens: set[str] = set()
        for value in values:
            for token in self._model_key_alias_tokens(value):
                tokens.add(token)
                stripped = self._strip_model_alias_suffix(token)
                if stripped:
                    tokens.update(self._model_key_alias_tokens(stripped))
        return tokens

    def _model_alias_priority(self, entry: ModelCatalogEntry) -> int:
        if entry.evaluation_kind is EvaluationKind.REGRESSION:
            return 0
        if entry.evaluation_kind is EvaluationKind.CLASSIFICATION:
            return 1
        task_order = {
            ModelTaskKind.SEGMENTER: 2,
            ModelTaskKind.TEXT_ANALYZER: 3,
            ModelTaskKind.RETRIEVER: 4,
            ModelTaskKind.ANOMALY_SCORER: 5,
            ModelTaskKind.RULE_MINER: 6,
            ModelTaskKind.RECOMMENDER: 7,
        }
        return task_order.get(entry.model_task_kind, 100)

    def _model_key_alias_tokens(self, value: str) -> list[str]:
        token = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
        while "__" in token:
            token = token.replace("__", "_")
        if not token:
            return []
        compact = token.replace("_", "")
        return [token] if compact == token else [token, compact]

    def _strip_model_alias_suffix(self, token: str) -> str:
        parts = token.split("_")
        if len(parts) > 1 and parts[-1] in _MODEL_ALIAS_SUFFIXES:
            return "_".join(parts[:-1])
        return ""

    def _model_key_error_message(self, field_name: str, failures: list[str]) -> str:
        return (
            f"{field_name} contains unsupported model keys: {', '.join(failures)}. "
            "Call model.metadata to inspect available canonical model keys. "
            f"Available keys: {', '.join(list_model_keys())}."
        )

    def _slug(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return normalized or "dataset"
