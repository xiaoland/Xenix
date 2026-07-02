from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent import ConversationStore
from xenix.services.agent.conversation_store import CreateToolCallInput, StartTurnInput
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_tokenization import DataTokenizationService, TokenizeDatasetInput
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.storage import StorageBootstrapService


def _build_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    dataset_service = DatasetService(context.session_factory, paths)
    data_cleaning_service = DataCleaningService(paths)
    data_tokenization_service = DataTokenizationService(paths)
    data_transform_service = DataQueryTransformService(paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        ml_task_service,
    )
    artifact_service = ArtifactService(context.session_factory)
    registry = AgentToolRegistry(
        paths=paths,
        dataset_service=dataset_service,
        data_cleaning_service=data_cleaning_service,
        data_tokenization_service=data_tokenization_service,
        data_transform_service=data_transform_service,
        ml_service=ml_service,
        artifact_service=artifact_service,
    )
    conversation_store = ConversationStore(context.session_factory)
    return paths, dataset_service, data_tokenization_service, artifact_service, registry, conversation_store


def _tool_context(
    conversation_store: ConversationStore,
    tool_name: str,
    arguments: dict,
) -> ToolExecutionContext:
    thread = conversation_store.create_thread()
    turn, _message = conversation_store.start_turn(
        StartTurnInput(
            thread_id=thread.id,
            user_content_blocks=[{"type": "text", "text": "Tokenize this dataset."}],
        )
    )
    _tool_message, tool_call = conversation_store.create_tool_call(
        CreateToolCallInput(
            thread_id=thread.id,
            turn_id=turn.id,
            tool_name=tool_name,
            arguments_payload=arguments,
        )
    )
    return ToolExecutionContext(
        thread_id=thread.id,
        turn_id=turn.id,
        tool_call_id=tool_call.id,
        dataset_ids=[],
    )


def test_data_tokenization_service_creates_token_text_dataset(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text(
        "review_id,review_text\n"
        "1,订单 退款 速度 快\n"
        "2,服务 热情 环境 舒适\n"
        "3,\n"
        "4,\n",
        encoding="utf-8",
    )

    result = tokenization_service.tokenize_dataset(
        TokenizeDatasetInput(
            source_path=str(source.resolve()),
            name="Reviews tokenized",
            text_column="review_text",
            output="token_text",
        )
    )

    frame = pd.read_csv(result.output_path, keep_default_na=False)

    assert frame.columns.tolist() == ["review_id", "review_text", "token_text", "token_count"]
    assert frame["token_text"].tolist() == ["订单 退款 速度", "服务 热情 环境 舒适", "", ""]
    assert frame["token_count"].tolist() == [3, 4, 0, 0]
    assert result.report == {
        "text_column": "review_text",
        "id_columns": [],
        "output": "token_text",
        "tokenizer_profile": "zh_business_v1",
        "source_row_count": 4,
        "output_row_count": 4,
        "tokenized_row_count": 2,
        "empty_token_row_count": 2,
        "token_count": 7,
    }


def test_data_tokenization_service_creates_token_rows_with_id_columns(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text(
        "review_id,channel,review_text\n"
        "r1,app,苹果 手机 包装 好\n"
        "r2,store,售后 退款 速度 慢\n",
        encoding="utf-8",
    )

    result = tokenization_service.tokenize_dataset(
        TokenizeDatasetInput(
            source_path=str(source.resolve()),
            name="Review tokens",
            text_column="review_text",
            id_columns=["review_id", "channel"],
            output="token_rows",
        )
    )

    frame = pd.read_csv(result.output_path, keep_default_na=False)

    assert frame.to_dict(orient="records") == [
        {"source_row_number": 1, "review_id": "r1", "channel": "app", "token_index": 1, "token": "苹果"},
        {"source_row_number": 1, "review_id": "r1", "channel": "app", "token_index": 2, "token": "手机"},
        {"source_row_number": 1, "review_id": "r1", "channel": "app", "token_index": 3, "token": "包装"},
        {"source_row_number": 2, "review_id": "r2", "channel": "store", "token_index": 1, "token": "售后"},
        {"source_row_number": 2, "review_id": "r2", "channel": "store", "token_index": 2, "token": "退款"},
        {"source_row_number": 2, "review_id": "r2", "channel": "store", "token_index": 3, "token": "速度"},
    ]
    assert result.report["output"] == "token_rows"
    assert result.report["output_row_count"] == 6
    assert result.report["token_count"] == 6


def test_data_tokenize_tool_registers_derived_dataset_and_artifact(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _tokenization_service, artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text(
        "review_id,review_text\n"
        "1,订单 退款 速度 快\n"
        "2,服务 热情 环境 舒适\n",
        encoding="utf-8",
    )
    source_dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            name="Reviews",
        )
    )
    arguments = {
        "dataset_id": source_dataset.id,
        "name": "Reviews tokenized",
        "text_column": "review_text",
        "output": "token_text",
    }
    context = _tool_context(store, "data.tokenize", arguments)

    result = registry.execute("data.tokenize", arguments, context)
    derived_dataset = dataset_service.get_dataset(result.payload["dataset_id"])
    resolved_artifact = artifact_service.resolve_uri(f"artifact://{result.payload['artifact_id']}")
    tokenized_frame = pd.read_csv(derived_dataset.source_path, keep_default_na=False)

    assert derived_dataset.derived_from_dataset_id == source_dataset.id
    assert derived_dataset.project_id == source_dataset.project_id
    assert tokenized_frame.columns.tolist() == ["review_id", "review_text", "token_text", "token_count"]
    assert result.payload["row_count"] == 2
    assert result.payload["tokenization_report"]["output"] == "token_text"
    assert resolved_artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert resolved_artifact.metadata_payload["derived_from_dataset_id"] == source_dataset.id
    assert resolved_artifact.metadata_payload["tokenization_report"]["tokenizer_profile"] == "zh_business_v1"
    assert "artifact_link" not in result.payload


def test_data_tokenize_tool_schema_is_dataset_scoped(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, _tokenization_service, _artifact_service, registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    specs = {spec.name: spec for spec in registry.list_specs()}

    assert "data.tokenize" in specs
    schema = specs["data.tokenize"].parameters_schema
    assert schema["required"] == ["dataset_id", "text_column"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {
        "dataset_id",
        "name",
        "text_column",
        "id_columns",
        "output",
        "tokenizer_profile",
    }
    assert schema["properties"]["output"]["enum"] == ["token_text", "token_rows"]
    assert schema["properties"]["tokenizer_profile"]["enum"] == ["zh_business_v1"]
    assert "jieba" not in str(schema)


def test_data_tokenize_tool_rejects_non_list_id_columns(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _tokenization_service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\n1,订单 退款\n", encoding="utf-8")
    source_dataset = dataset_service.register_dataset(
        RegisterDatasetInput(
            source_path=str(source.resolve()),
            name="Reviews",
        )
    )
    arguments = {
        "dataset_id": source_dataset.id,
        "text_column": "review_text",
        "id_columns": "review_id",
    }
    context = _tool_context(store, "data.tokenize", arguments)

    with pytest.raises(ValidationError, match="id_columns must be a list of strings"):
        registry.execute("data.tokenize", arguments, context)
