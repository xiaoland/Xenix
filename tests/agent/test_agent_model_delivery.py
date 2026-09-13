from types import SimpleNamespace

import pytest

from xenix.services.agent._model_tools import ModelTools
from xenix.services.agent.tool_inputs import ModelApplyInput, ModelHyperTrainInput, ModelMetadataInput, ModelTrainInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.storage.models import MLTaskArtifactKind


@pytest.mark.parametrize("tune", [False, True])
def test_completed_training_exposes_evaluation_report_without_an_extra_query(tune):
    fit = SimpleNamespace(id="fit", result_payload={"trained_model_id": "model"})
    evaluation = SimpleNamespace(id="evaluation", result_payload={"metric": 0.9})
    report = SimpleNamespace(artifact_id="public-report", artifact_kind=MLTaskArtifactKind.EVALUATION_REPORT)
    ml = SimpleNamespace(
        get_column_binding=lambda _id: SimpleNamespace(dataset_id="source"),
        fit_with_evaluate=lambda _input: fit,
        tune_with_evaluate=lambda _input: fit,
        wait_for_training_models=lambda *_args, **_kwargs: (
            [fit, evaluation], [SimpleNamespace(
                id="model", ml_task_id="fit", model_key="regression.ridge",
                metadata_payload={"evaluation_ml_task_id": "evaluation"},
            )],
        ),
        get_task_details=lambda task_id: SimpleNamespace(artifacts=[report] if task_id == "evaluation" else []),
    )
    tools = ModelTools(paths=None, dataset_service=None, artifact_service=None, ml_service=ml,
                       model_key_aliases={"regression.ridge": "regression.ridge"})
    context = ToolExecutionContext(thread_id="thread", tool_call_message_id="call")
    if tune:
        result = tools._model_hyper_train(ModelHyperTrainInput(
            binding_id="binding", param_grids_by_model={"regression.ridge": {"alpha": [1.0]}},
        ), context)
    else:
        result = tools._model_train(ModelTrainInput(binding_id="binding", models=["regression.ridge"]), context)
    assert any(item["uri"] == "artifact://public-report" and item["ml_task_id"] == "evaluation"
               for item in result.value["artifacts"])


def test_apply_delivers_finalized_dataset_and_facts_without_task_query():
    payload = {
        "task_id": "apply", "trained_model_id": "model", "model_key": "forecasting.holt_winters",
        "output_file_path": "worker-output.csv", "canonical_output_path": "derived.parquet",
        "result_dataset_id": "forecast-dataset", "row_count": 12,
        "summary": {"row_count": 12, "input_file_count": 0, "apply_mode": "future_horizon",
                    "horizon": 6, "group_count": 2},
    }
    task = SimpleNamespace(id="apply", result_payload=payload)
    artifact = SimpleNamespace(artifact_id="forecast-workbook", artifact_kind=MLTaskArtifactKind.APPLY_RESULT)
    ml = SimpleNamespace(
        apply=lambda _input: task,
        wait_for_task=lambda *_args, **_kwargs: task,
        get_task_details=lambda _id: SimpleNamespace(task=task, artifacts=[artifact]),
    )
    tools = ModelTools(paths=None, dataset_service=None, artifact_service=None, ml_service=ml, model_key_aliases={})
    result = tools._model_apply(ModelApplyInput(trained_model_id="model", horizon=6),
                                ToolExecutionContext(thread_id="thread", tool_call_message_id="call")).value
    assert result["result_dataset_id"] == "forecast-dataset"
    assert result["result"]["result_dataset_id"] == result["result_dataset_id"]
    assert result["uri"] == "artifact://forecast-workbook"
    assert result["result"]["row_count"] == 12
    assert result["result"]["summary"] == payload["summary"]
    assert "output_file_path" not in result["result"]
    assert payload["canonical_output_path"] == "derived.parquet"


def test_family_metadata_can_deliver_candidate_training_contracts_together():
    tools = ModelTools(paths=None, dataset_service=None, artifact_service=None,
                       ml_service=SimpleNamespace(), model_key_aliases={})
    context = ToolExecutionContext(thread_id="thread", tool_call_message_id="call")
    models = tools._model_metadata(ModelMetadataInput(model_family="forecasting", include_details=True), context).value["models"]
    assert len(models) >= 2
    for model in models:
        direct = tools._model_metadata(ModelMetadataInput(model_key=model["model_key"]), context).value["models"][0]
        assert model == direct
        assert model["param_schema"]
