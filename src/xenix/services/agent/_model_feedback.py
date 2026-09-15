"""Decision evidence for model Tools, projected from persisted ML results."""

from __future__ import annotations

from typing import Any

from ..storage.models import MLTaskRow, TrainedModelRow


def training_feedback(
    tasks: list[MLTaskRow], trained_models: list[TrainedModelRow],
) -> list[dict[str, Any]]:
    """Associate each retained candidate with its settled training/evaluation facts."""
    tasks_by_id = {task.id: task for task in tasks}
    models = []
    for model in trained_models:
        training = tasks_by_id[model.ml_task_id]
        evaluation_id = model.metadata_payload.get("evaluation_ml_task_id")
        # Evaluation replaces the corresponding FIT facts, rather than repeating
        # both records or implying that they are independent validation samples.
        facts = dict(training.result_payload or {})
        if evaluation_id is not None:
            facts.update({
                key: value for key, value in (tasks_by_id[evaluation_id].result_payload or {}).items()
                if value is not None
            })
        models.append({
            "trained_model_id": model.id,
            "model_key": model.model_key,
            "training_task_id": training.id,
            "evaluation_task_id": evaluation_id,
            **training_result_summary(facts),
        })
    return models


def training_result_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Keep selection, evaluation and reuse facts; full diagnostics stay in ML storage."""
    summary = {
        key: result[key]
        for key in (
            "model_key", "trained_model_id", "evaluation_kind", "params", "best_params",
            "training_scopes", "tuning_summary", "comparison", "error_summary", "cross_validation",
        )
        if result.get(key) is not None
    }
    for key in ("evaluation", "baseline_evaluation"):
        metrics = result.get(key)
        if metrics is not None:
            # Metric/label names are business data, not internal schema keys.
            summary[key] = {
                **metrics,
                "details": {
                    name: value for name, value in metrics.get("details", {}).items()
                    if not name.endswith("_digest")
                },
            }
    for key in (
        "result_summary", "split_facts", "forecast_split_facts",
        "recommendation_split_facts", "forecast_evaluation", "clustering_evaluation",
        "recommendation_evaluation", "text_classification_evaluation",
        "text_clustering_evaluation", "text_topic_evaluation", "text_retrieval_evaluation",
    ):
        if result.get(key) is not None:
            summary[key] = _fact_summary(result[key])
    return summary


def _fact_summary(value: Any) -> Any:
    """Omit mechanical identities from ML-owned fact trees, preserving evidence and limitations."""
    if isinstance(value, list):
        return [_fact_summary(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: item if key in {"metrics", "baseline_metrics"} else _fact_summary(item)
        for key, item in value.items()
        if not key.endswith("_digest")
        and key not in {"digest", "schema_version", "protocol", "protocol_key", "policy_key", "specification"}
    }
