from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.exceptions import ValidationError
from xenix.services.agent.tool_inputs import AnalysisProfileInput
from xenix.services.agent.tools import AgentToolRegistry
from xenix.services.analysis_profile import (
    AnalysisProfileService,
    MAX_PROFILE_FIELD_LIMIT,
    ProfileDatasetInput,
    render_dataset_profile_markdown,
)
from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
from xenix.services.llm.tooling import ToolExecutionContext
from xenix.services.storage import StorageBootstrapService
from xenix.services.tabular import TabularRuntimeError


def _write_mixed_csv(tmp_path: Path) -> Path:
    source = tmp_path / "sales.csv"
    source.write_text(
        "\n".join(
            [
                "customer_id,region,amount,score,active,date",
                "C-001,North,10,1.5,1,2026-01-01",
                "C-002,South,20,2.5,0,2026-01-02",
                "C-003,North,,2.0,1,2026-01-03",
                "C-004,South,20,3.0,0,2026-01-04",
                "C-004,South,20,3.0,0,2026-01-04",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return source


def _registered_dataset(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    datasets = DatasetService(context.session_factory, paths)
    source = _write_mixed_csv(tmp_path)
    dataset = datasets.register_dataset(
        RegisterDatasetInput(source_path=str(source.resolve()), name="Sales")
    )
    return paths, datasets, dataset


def test_analysis_profile_service_returns_typed_bounded_value_safe_facts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _paths, datasets, dataset = _registered_dataset(monkeypatch, tmp_path)

    result = AnalysisProfileService(datasets).profile_dataset(
        ProfileDatasetInput(
            dataset_id=dataset.id,
            field_limit=6,
            numeric_summary_limit=2,
            correlation_column_limit=2,
        )
    )

    assert result.dataset_id == dataset.id
    assert result.scope == "whole_dataset"
    assert result.basic.model_dump() == {
        "row_count": 5,
        "column_count": 6,
        "exact_duplicate_row_count": 1,
    }
    assert [field.index for field in result.fields] == list(range(6))
    assert [field.name for field in result.fields] == [
        "customer_id",
        "region",
        "amount",
        "score",
        "active",
        "date",
    ]
    assert [field.logical_type for field in result.fields] == [
        "identifier",
        "categorical_text",
        "continuous_numeric",
        "continuous_numeric",
        "binary",
        "datetime",
    ]
    assert result.fields[2].missing_count == 1
    assert result.fields[2].missing_rate == 0.2
    assert [summary.field_name for summary in result.numeric_summaries] == ["amount", "score"]
    assert result.datetime_ranges[0].model_dump() == {
        "field_index": 5,
        "field_name": "date",
        "earliest": "2026-01-01T00:00:00",
        "latest": "2026-01-04T00:00:00",
        "span_days": 3,
    }
    assert result.correlations.eligible_field_count == 2
    assert result.correlations.included_field_count == 2
    assert result.correlations.truncated is False
    assert len(result.correlations.facts) == 1

    provider_projection = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    for forbidden in ("C-001", "C-004", "North", "South", "sales.csv", str(dataset.source_path)):
        assert forbidden not in provider_projection
    assert "category_frequencies" not in provider_projection
    assert "target_group_statistics" not in provider_projection
    assert "sample" not in provider_projection
    assert "preview" not in provider_projection

    markdown = render_dataset_profile_markdown(result)
    assert f"# Dataset profile: {dataset.id}" in markdown
    assert "| Exact duplicate rows | 1 |" in markdown
    assert "North" not in markdown
    assert "C-001" not in markdown


def test_analysis_profile_service_exposes_explicit_truncation(monkeypatch, tmp_path: Path) -> None:
    _paths, datasets, dataset = _registered_dataset(monkeypatch, tmp_path)

    result = AnalysisProfileService(datasets).profile_dataset(
        ProfileDatasetInput(
            dataset_id=dataset.id,
            field_limit=3,
            numeric_summary_limit=1,
            correlation_column_limit=2,
        )
    )

    assert result.truncation.fields.model_dump() == {
        "total_count": 6,
        "returned_count": 3,
        "truncated": True,
    }
    assert result.truncation.numeric_summaries.model_dump() == {
        "total_count": 2,
        "returned_count": 1,
        "truncated": True,
    }
    with pytest.raises(ValueError):
        ProfileDatasetInput(
            dataset_id=dataset.id,
            field_limit=MAX_PROFILE_FIELD_LIMIT + 1,
        )


def test_analysis_profile_is_registered_as_one_atomic_read_only_tool(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths, datasets, dataset = _registered_dataset(monkeypatch, tmp_path)
    data_transform = Mock()
    registry = AgentToolRegistry(
        paths=paths,
        dataset_service=datasets,
        data_cleaning_service=Mock(),
        data_transform_service=data_transform,
        ml_service=Mock(),
        artifact_service=Mock(),
    )

    spec = next(spec for spec in registry.list_specs() if spec.name == "analysis.profile")
    assert spec.provider_name == "analysis_profile"
    assert set(spec.parameters_schema["properties"]) == {
        "dataset_id",
        "field_limit",
        "numeric_summary_limit",
        "correlation_column_limit",
    }
    assert "source_path" not in json.dumps(spec.parameters_schema)
    assert AnalysisProfileInput.model_validate({"dataset_id": dataset.id}).dataset_id == dataset.id

    outcome = registry.execute(
        "analysis.profile",
        {"dataset_id": dataset.id},
        ToolExecutionContext(thread_id="thread-profile", dataset_ids=(dataset.id,)),
    )

    assert isinstance(outcome.value, dict)
    assert outcome.value["dataset_id"] == dataset.id
    assert outcome.value["scope"] == "whole_dataset"
    assert not data_transform.mock_calls
    assert datasets.list_derived_datasets(dataset.id) == []


def test_analysis_profile_service_surfaces_path_safe_structured_runtime_error(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    _paths, datasets, dataset = _registered_dataset(monkeypatch, tmp_path)

    def fail_load(*_args, **_kwargs):
        raise TabularRuntimeError(
            "Polars failed to read the registered dataset.",
            error_details={
                "engine": "polars",
                "phase": "read",
                "package_versions": {
                    "polars": "1.42.1",
                    "polars-runtime-32": "1.41.2",
                },
            },
        )

    monkeypatch.setattr("xenix.services.analysis_profile.load_tabular_frame", fail_load)

    with caplog.at_level("ERROR", logger="xenix.services.analysis_profile"):
        with pytest.raises(ValidationError) as exc_info:
            AnalysisProfileService(datasets).profile_dataset(
                ProfileDatasetInput(dataset_id=dataset.id)
            )

    assert f"dataset {dataset.id}" in caplog.text
    assert exc_info.value.error_code == "tabular_runtime_unavailable"
    assert exc_info.value.error_details["operation"] == "analysis.profile"
    assert exc_info.value.error_details["dataset_id"] == dataset.id
    assert "source_path" not in exc_info.value.error_details
    assert exc_info.value.error_details["tabular"]["package_versions"]["polars-runtime-32"] == "1.41.2"
    assert any("data.query" in hint for hint in exc_info.value.repair_hints)
    assert exc_info.value.retryable is True
