from types import SimpleNamespace

import pytest

from xenix.services.agent._model_tools import ModelTools
from xenix.services.agent.tool_inputs import ModelApplyInput, ModelHyperTrainInput, ModelMetadataInput, ModelTrainInput
from xenix.services.llm.tool_protocol import ToolExecutionContext
from xenix.services.storage.models import MLTaskArtifactKind


@pytest.mark.parametrize("tune", [False, True])
def test_completed_training_exposes_evaluation_report_without_an_extra_query(tune):
    fit = SimpleNamespace(id=104, result_payload={"trained_model_id": 102})
    evaluation = SimpleNamespace(id=105, result_payload={"metric": 0.9})
    report = SimpleNamespace(artifact_id=106, artifact_kind=MLTaskArtifactKind.EVALUATION_REPORT)
    ml = SimpleNamespace(
        get_column_binding=lambda _id: SimpleNamespace(dataset_id=111),
        fit_with_evaluate=lambda _input: fit,
        tune_with_evaluate=lambda _input: fit,
        wait_for_training_models=lambda *_args, **_kwargs: (
            [fit, evaluation], [SimpleNamespace(
                id=102, ml_task_id=104, model_key="regression.ridge",
                metadata_payload={"evaluation_ml_task_id": 105},
            )],
        ),
        get_task_details=lambda task_id: SimpleNamespace(artifacts=[report] if task_id == 105 else []),
    )
    tools = ModelTools(paths=None, dataset_service=None, artifact_service=None, ml_service=ml,
                       model_key_aliases={"regression.ridge": "regression.ridge"})
    context = ToolExecutionContext(thread_id=107, tool_call_message_id=108)
    if tune:
        result = tools._model_hyper_train(ModelHyperTrainInput(
            binding_id=110, explanations_by_model={"regression.ridge": "Use regularization to reduce overfitting."}, param_grids_by_model={"regression.ridge": {"alpha": [1.0]}},
        ), context)
    else:
        result = tools._model_train(ModelTrainInput(binding_id=110, explanations_by_model={"regression.ridge": "Use regularization to reduce overfitting."}, models=["regression.ridge"]), context)
    assert any(item["uri"] == 'artifact://106' and item["ml_task_id"] == 105
               for item in result.value["artifacts"])


def test_apply_delivers_finalized_dataset_and_facts_without_task_query():
    payload = {
        "task_id": 101, "trained_model_id": 102, "model_key": "forecasting.holt_winters",
        "output_file_path": "worker-output.csv", "canonical_output_path": "derived.parquet",
        "result_dataset_id": 103, "row_count": 12,
        "summary": {"row_count": 12, "input_file_count": 0, "apply_mode": "future_horizon",
                    "horizon": 6, "group_count": 2},
    }
    task = SimpleNamespace(id=101, result_payload=payload)
    artifact = SimpleNamespace(artifact_id=109, artifact_kind=MLTaskArtifactKind.APPLY_RESULT)
    ml = SimpleNamespace(
        apply=lambda _input: task,
        wait_for_task=lambda *_args, **_kwargs: task,
        get_task_details=lambda _id: SimpleNamespace(task=task, artifacts=[artifact]),
    )
    tools = ModelTools(paths=None, dataset_service=None, artifact_service=None, ml_service=ml, model_key_aliases={})
    result = tools._model_apply(ModelApplyInput(trained_model_id=102, horizon=6, explanation="Forecast six periods for replenishment planning."),
                                ToolExecutionContext(thread_id=107, tool_call_message_id=108)).value
    assert result["result_dataset_id"] == 103
    assert result["result"]["result_dataset_id"] == result["result_dataset_id"]
    assert result["uri"] == 'artifact://109'
    assert result["result"]["row_count"] == 12
    assert result["result"]["summary"] == payload["summary"]
    assert "output_file_path" not in result["result"]
    assert payload["canonical_output_path"] == "derived.parquet"


def test_family_metadata_can_deliver_candidate_training_contracts_together():
    tools = ModelTools(paths=None, dataset_service=None, artifact_service=None,
                       ml_service=SimpleNamespace(), model_key_aliases={})
    context = ToolExecutionContext(thread_id=107, tool_call_message_id=108)
    models = tools._model_metadata(ModelMetadataInput(model_family="forecasting", include_details=True), context).value["models"]
    assert len(models) >= 2
    for model in models:
        direct = tools._model_metadata(ModelMetadataInput(model_key=model["model_key"]), context).value["models"][0]
        assert model == direct
        assert model["param_schema"]
