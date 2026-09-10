from types import SimpleNamespace

import pytest

from xenix.services.agent._model_tools import ModelTools
from xenix.services.agent.tool_inputs import ModelHyperTrainInput, ModelTrainInput
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
            [fit, evaluation], [SimpleNamespace(id="model")],
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

