import re
from pathlib import Path

import pandas as pd
import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent.tools import AgentToolRegistry, ToolExecutionContext
from xenix.services.artifact_service import ArtifactService
from xenix.services.data_cleaning import DataCleaningService
from xenix.services.data_tokenization import DataTokenizationService, TokenizeDatasetInput
from xenix.services.data_transform import DataQueryTransformService
from xenix.services.dataset_inspection import detect_source_format, load_dataframe
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.preprocessing_worker import InlinePreprocessingWorkerRunner
from xenix.services.storage import StorageBootstrapService


def _build_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    dataset_service = DatasetService(context.session_factory, paths)
    worker_runner = InlinePreprocessingWorkerRunner()
    data_cleaning_service = DataCleaningService(paths, worker_runner=worker_runner)
    data_tokenization_service = DataTokenizationService(paths)
    data_transform_service = DataQueryTransformService(paths, worker_runner=worker_runner)
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
        preprocessing_worker_runner=worker_runner,
    )
    return paths, dataset_service, data_tokenization_service, artifact_service, registry, None


def _tool_context(
    _conversation_store,
    tool_name: str,
    arguments: dict,
) -> ToolExecutionContext:
    return ToolExecutionContext(
        thread_id="tool-test-thread",
        dataset_ids=(),
    )


def _read_dataset_frame(path: str | Path) -> pd.DataFrame:
    source_path = Path(path)
    return load_dataframe(source_path, detect_source_format(source_path))


def _xtt_metadata(value: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}: (.+)$", value, re.MULTILINE)
    assert match is not None, f"missing XTT metadata field {key!r}: {value}"
    return match.group(1)


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
    assert isinstance(result.value, str)
    derived_dataset = dataset_service.get_dataset(_xtt_metadata(result.value, "dataset_id"))
    tokenized_frame = _read_dataset_frame(derived_dataset.source_path).fillna("")

    assert derived_dataset.derived_from_dataset_id == source_dataset.id
    assert derived_dataset.project_id == source_dataset.project_id
    assert "dataset_uri" not in result.value
    assert "artifact_uri" not in result.value
    artifact = artifact_service.resolve_uri(f"artifact://{_xtt_metadata(result.value, 'artifact_id')}")
    assert artifact.metadata_payload["dataset_id"] == derived_dataset.id
    assert artifact.metadata_payload["dataset_export"]["dataset_id"] == derived_dataset.id
    assert pd.read_excel(artifact.absolute_path).columns.tolist() == [
        "review_id",
        "review_text",
        "token_text",
        "token_count",
    ]
    assert tokenized_frame.columns.tolist() == ["review_id", "review_text", "token_text", "token_count"]
    assert "row_count: 2" in result.value
    assert "output: token_text" in result.value
    assert "artifact_link" not in result.value


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


def test_data_tokenization_service_resolves_column_indexes_to_canonical_names(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text(
        "review_id,,review_text\n"
        "r1,app,苹果 手机 包装 好\n",
        encoding="utf-8",
    )

    result = tokenization_service.tokenize_dataset(
        TokenizeDatasetInput(
            source_path=str(source.resolve()),
            name="Review tokens",
            text_column_index=2,
            id_column_indexes=[0, 1],
            output="token_rows",
        )
    )

    frame = pd.read_csv(result.output_path, keep_default_na=False)
    assert frame.columns.tolist() == [
        "source_row_number",
        "review_id",
        "column_2",
        "token_index",
        "token",
    ]
    assert result.report["text_column"] == "review_text"
    assert result.report["id_columns"] == ["review_id", "column_2"]


def test_data_tokenization_canonicalizes_duplicate_unicode_headers_positionally(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "unicode-headers.csv"
    source.write_text(
        "订单号,订单号,评价文本\n"
        "r1,web,苹果 手机\n",
        encoding="utf-8",
    )

    result = tokenization_service.tokenize_dataset(
        TokenizeDatasetInput(
            source_path=str(source.resolve()),
            name="Unicode header tokens",
            text_column_index=2,
            id_column_indexes=[0, 1],
            output="token_rows",
        )
    )

    frame = pd.read_csv(result.output_path, keep_default_na=False)
    assert frame.columns.tolist() == [
        "source_row_number",
        "订单号",
        "column_2",
        "token_index",
        "token",
    ]
    assert result.report["text_column"] == "评价文本"
    assert result.report["id_columns"] == ["订单号", "column_2"]


def test_data_tokenization_service_allows_mixed_selector_modes_per_field(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\nr1,订单 退款\n", encoding="utf-8")

    result = tokenization_service.tokenize_dataset(
        TokenizeDatasetInput(
            source_path=str(source.resolve()),
            name="Review tokens",
            text_column="review_text",
            id_column_indexes=[0],
            output="token_rows",
        )
    )

    assert result.report["text_column"] == "review_text"
    assert result.report["id_columns"] == ["review_id"]


def test_data_tokenization_service_accepts_empty_id_column_indexes(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\nr1,订单 退款\n", encoding="utf-8")

    result = tokenization_service.tokenize_dataset(
        TokenizeDatasetInput(
            source_path=str(source.resolve()),
            name="Review tokens",
            text_column_index=1,
            id_column_indexes=[],
            output="token_rows",
        )
    )

    assert result.report["id_columns"] == []


@pytest.mark.parametrize(
    ("text_column_index", "id_column_indexes", "message"),
    [
        (1, [0, 0], "cannot contain duplicates"),
        (1, [1], "cannot include text_column"),
    ],
)
def test_data_tokenization_service_rejects_invalid_resolved_id_indexes(
    monkeypatch,
    tmp_path: Path,
    text_column_index: int,
    id_column_indexes: list[int],
    message: str,
) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\nr1,订单 退款\n", encoding="utf-8")

    with pytest.raises(ValidationError, match=message):
        tokenization_service.tokenize_dataset(
            TokenizeDatasetInput(
                source_path=str(source.resolve()),
                name="Review tokens",
                text_column_index=text_column_index,
                id_column_indexes=id_column_indexes,
                output="token_rows",
            )
        )


@pytest.mark.parametrize("bad_index", [True, "1", 1.0, -1, 3])
def test_data_tokenization_service_rejects_invalid_text_column_indexes(
    monkeypatch,
    tmp_path: Path,
    bad_index: object,
) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\nr1,订单 退款\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="text_column_index"):
        tokenization_service.tokenize_dataset(
            TokenizeDatasetInput(
                source_path=str(source.resolve()),
                name="Review tokens",
                text_column_index=bad_index,
            )
        )


def test_data_tokenization_service_rejects_mixed_column_reference_forms(monkeypatch, tmp_path: Path) -> None:
    _paths, _dataset_service, tokenization_service, _artifact_service, _registry, _store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\nr1,订单 退款\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="either text_column or text_column_index"):
        tokenization_service.tokenize_dataset(
            TokenizeDatasetInput(
                source_path=str(source.resolve()),
                name="Review tokens",
                text_column="review_text",
                text_column_index=1,
            )
        )
    with pytest.raises(ValidationError, match="either id_columns or id_column_indexes"):
        tokenization_service.tokenize_dataset(
            TokenizeDatasetInput(
                source_path=str(source.resolve()),
                name="Review tokens",
                text_column="review_text",
                id_columns=[],
                id_column_indexes=[],
                output="token_rows",
            )
        )


def test_data_tokenize_tool_rejects_mixed_selector_forms(monkeypatch, tmp_path: Path) -> None:
    _paths, dataset_service, _tokenization_service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\nr1,订单 退款\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Reviews")
    )
    context = _tool_context(store, "data.tokenize", {})

    with pytest.raises(ValidationError, match="either text_column or text_column_index"):
        registry.execute(
            "data.tokenize",
            {"dataset_id": dataset.id, "text_column": "review_text", "text_column_index": 1},
            context,
        )
    with pytest.raises(ValidationError, match="either id_columns or id_column_indexes"):
        registry.execute(
            "data.tokenize",
            {
                "dataset_id": dataset.id,
                "text_column_index": 1,
                "id_columns": [],
                "id_column_indexes": [],
            },
            context,
        )


@pytest.mark.parametrize(
    ("selector_arguments", "message"),
    [
        ({"text_column_index": True}, "text_column_index must be a zero-based integer"),
        (
            {"text_column_index": 1, "id_column_indexes": [True]},
            "id_column_indexes must contain zero-based integers",
        ),
        (
            {"text_column_index": 1, "id_column_indexes": [2]},
            "id_column_indexes index 2 is outside the available zero-based column range",
        ),
    ],
)
def test_data_tokenize_tool_rejects_invalid_index_selectors(
    monkeypatch,
    tmp_path: Path,
    selector_arguments: dict[str, object],
    message: str,
) -> None:
    _paths, dataset_service, _tokenization_service, _artifact_service, registry, store = _build_runtime(
        monkeypatch,
        tmp_path,
    )
    source = tmp_path / "reviews.csv"
    source.write_text("review_id,review_text\nr1,订单 退款\n", encoding="utf-8")
    dataset = dataset_service.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Reviews")
    )
    arguments = {"dataset_id": dataset.id, **selector_arguments}

    with pytest.raises(ValidationError, match=message):
        registry.execute("data.tokenize", arguments, _tool_context(store, "data.tokenize", arguments))
