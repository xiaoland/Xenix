"""Offline proof for the opt-in real-provider Agent Harness benchmark."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import polars as pl
import pytest

from agent_harness_benchmark.cleaning_april import (
    AprilDineInSalesCleaningCase,
    AprilSourceState,
    BenchmarkInputError,
)
from agent_harness_benchmark.contracts import (
    AgentHarnessBenchmarkResult,
    BenchmarkIdentity,
    BenchmarkMetrics,
    BenchmarkRunStatus,
)
from agent_harness_benchmark import runner
from xenix.services.llm.messages import DatasetBlock, blocks_to_json
from xenix.services.storage.models import DatasetSourceFormat


class _DatasetService:
    def __init__(self, datasets: list[SimpleNamespace]) -> None:
        self._datasets = {dataset.id: dataset for dataset in datasets}

    def get_dataset(self, dataset_id: str) -> SimpleNamespace:
        return self._datasets[dataset_id]

    def list_datasets(self) -> list[SimpleNamespace]:
        return list(self._datasets.values())

    def list_generated_datasets(self) -> list[SimpleNamespace]:
        return list(self._datasets.values())


class _InvalidFixtureCase:
    case_id = "test.invalid_fixture"

    def validate_input(self) -> str:
        raise BenchmarkInputError("fixture_hash_mismatch")


class _PassingCase:
    case_id = "test.matrix"

    def validate_input(self) -> str:
        return "fixture-hash"


def _dataset(dataset_id: str, path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=dataset_id,
        source_path=str(path),
        source_format=DatasetSourceFormat.PARQUET,
    )


def _message(kind: str, **values: object) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, **values)


def _snapshot_with_source_and_output(output_value: object) -> SimpleNamespace:
    source = DatasetBlock(dataset_id="source", name="source", row_count=3, column_count=2)
    return SimpleNamespace(
        messages=[
            _message("user", content_payload={"blocks": blocks_to_json([source])}),
            _message("tool_result", result_status="succeeded", value_payload=output_value),
            _message("assistant", refusal=None),
        ]
    )


def _settings_file(tmp_path: Path, *, models: list[str] | None = None) -> Path:
    settings_path = tmp_path / "benchmark-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "key": "benchmark",
                        "display_name": "Benchmark",
                        "base_url": "https://endpoint.example.test",
                        "api_key": "benchmark-secret-must-not-leak",
                        "models": models or ["one", "two"],
                    }
                ],
                "default_fq_model_key": "benchmark/one",
            }
        ),
        encoding="utf-8",
    )
    return settings_path


def test_locator_uses_latest_readable_run_created_tool_result_reference(tmp_path: Path) -> None:
    source_path = tmp_path / "source.parquet"
    derived_path = tmp_path / "derived.parquet"
    pl.DataFrame({"a": [1]}).write_parquet(source_path)
    pl.DataFrame({"a": [2]}).write_parquet(derived_path)
    service = _DatasetService([_dataset("source", source_path), _dataset("derived", derived_path)])
    snapshot = _snapshot_with_source_and_output("dataset_id: derived\n\nshape: 1 rows × 1 columns")
    case = AprilDineInSalesCleaningCase(tmp_path / "unused.xlsx")

    resolved = case._resolve_terminal_dataset(  # noqa: SLF001 - case-owned public behavior proof
        snapshot=snapshot,
        dataset_service=service,
        source_dataset_ids={"source"},
        run_dataset_ids={"source", "derived"},
    )

    assert resolved is not None
    assert resolved[0].id == "derived"
    assert resolved[1].to_dicts() == [{"a": 2}]


def test_locator_skips_unreadable_or_source_only_references(tmp_path: Path) -> None:
    source_path = tmp_path / "source.parquet"
    pl.DataFrame({"a": [1]}).write_parquet(source_path)
    service = _DatasetService([_dataset("source", source_path)])
    case = AprilDineInSalesCleaningCase(tmp_path / "unused.xlsx")

    unreadable = _snapshot_with_source_and_output("dataset_id: missing\n\nshape: 1 rows × 1 columns")
    source_only = _snapshot_with_source_and_output({"dataset_id": "source"})

    assert case._resolve_terminal_dataset(  # noqa: SLF001 - case-owned behavior proof
        snapshot=unreadable,
        dataset_service=service,
        source_dataset_ids={"source"},
        run_dataset_ids={"source", "missing"},
    ) is None
    assert case._resolve_terminal_dataset(  # noqa: SLF001 - case-owned behavior proof
        snapshot=source_only,
        dataset_service=service,
        source_dataset_ids={"source"},
        run_dataset_ids={"source"},
    ) is None


def test_cleaning_oracle_checks_terminal_data_without_prescribing_tool_sequence(tmp_path: Path) -> None:
    external_source = tmp_path / "external.xlsx"
    external_source.write_bytes(b"external-source")
    source_path = tmp_path / "source.parquet"
    output_path = tmp_path / "output.parquet"
    pl.DataFrame(
        {
            "placeholder": ["report filter", "city", "A", "B", "B"],
            "column_2": ["--", "amount", "1", "2", "2"],
        }
    ).write_parquet(source_path)
    pl.DataFrame({"city": ["A", "B"], "amount": ["1", "2"]}).write_parquet(output_path)
    service = _DatasetService([_dataset("source", source_path), _dataset("derived", output_path)])
    source_digest = sha256(source_path.read_bytes()).hexdigest().upper()
    external_digest = sha256(external_source.read_bytes()).hexdigest().upper()
    case = AprilDineInSalesCleaningCase(external_source)

    assessment = case.assess(
        snapshot=_snapshot_with_source_and_output("dataset_id: derived\n\nshape: 2 rows × 2 columns"),
        dataset_service=service,
        source_state=AprilSourceState(
            external_sha256=external_digest,
            source_dataset_ids=("source",),
            registered_dataset_sha256={"source": source_digest},
        ),
        run_dataset_ids={"source", "derived"},
        runtime_home=tmp_path,
        settings_unchanged=True,
    )
    checks = {check.name: check for check in assessment.checks}

    assert assessment.terminal_shape == (2, 2)
    assert checks["canonical_completion"].passed is True
    assert checks["terminal_output_resolved"].passed is True
    assert checks["header_promoted"].passed is True
    assert checks["report_row_removed"].passed is True
    assert checks["header_row_removed"].passed is True
    assert checks["exact_duplicates_removed"].passed is True
    assert checks["business_rows_preserved"].passed is True
    assert checks["expected_shape"].passed is False
    assert checks["source_unchanged"].passed is True
    assert checks["state_isolated"].passed is True


def test_settings_matrix_expands_all_models_and_dry_run_never_prints_credentials(tmp_path: Path) -> None:
    settings_path = _settings_file(tmp_path)
    settings, settings_sha256 = runner.load_settings_snapshot(settings_path)

    assert runner.configured_model_keys(settings) == ("benchmark/one", "benchmark/two")
    assert runner.dry_run_models(settings_path=settings_path) == ("benchmark/one", "benchmark/two")
    assert len(settings_sha256) == 64

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_agent_harness_benchmark.py",
            "--llm-settings",
            str(settings_path),
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == ["benchmark/one", "benchmark/two"]
    assert "benchmark-secret-must-not-leak" not in completed.stdout
    assert "endpoint.example.test" not in completed.stdout


def test_dry_run_reads_the_external_settings_path_from_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    settings_path = _settings_file(tmp_path)
    monkeypatch.setenv(runner.LLM_SETTINGS_PATH_ENV, str(settings_path))

    assert runner.dry_run_models() == ("benchmark/one", "benchmark/two")


def test_invalid_fixture_persists_one_safe_result_per_configured_model(tmp_path: Path) -> None:
    settings_path = _settings_file(tmp_path)
    output_directory = tmp_path / "results"

    runs = runner.run_benchmark(
        settings_path=settings_path,
        source_path=tmp_path / "unused.xlsx",
        output_directory=output_directory,
        case=_InvalidFixtureCase(),
    )

    assert [run.result.provider_model for run in runs] == ["benchmark/one", "benchmark/two"]
    assert all(run.persisted for run in runs)
    assert all(run.result.run_status is BenchmarkRunStatus.INVALID_SETUP for run in runs)
    payload = json.dumps(runs[0].result.to_payload(), ensure_ascii=False)
    assert "benchmark-secret-must-not-leak" not in payload
    assert "endpoint.example.test" not in payload
    assert "unused.xlsx" not in payload
    assert len(list(output_directory.glob("*.json"))) == 2


def test_matrix_continues_after_one_cell_result(tmp_path: Path, monkeypatch) -> None:
    settings_path = _settings_file(tmp_path)
    observed_models: list[str] = []

    def fake_run_model_cell(**arguments):
        model_key = arguments["model_key"]
        observed_models.append(model_key)
        return AgentHarnessBenchmarkResult(
            case_id="test.matrix",
            run_id=f"run-{len(observed_models)}",
            provider_model=model_key,
            run_status=BenchmarkRunStatus.RUNTIME_ERROR if model_key.endswith("one") else BenchmarkRunStatus.COMPLETED,
            metrics=BenchmarkMetrics(),
            identity=arguments["identity"],
            failure_kind="synthetic_runtime_error" if model_key.endswith("one") else None,
        )

    monkeypatch.setattr(runner, "_run_model_cell", fake_run_model_cell)
    runs = runner.run_benchmark(
        settings_path=settings_path,
        source_path=tmp_path / "unused.xlsx",
        output_directory=tmp_path / "results",
        case=_PassingCase(),
    )

    assert observed_models == ["benchmark/one", "benchmark/two"]
    assert [run.result.run_status for run in runs] == [
        BenchmarkRunStatus.RUNTIME_ERROR,
        BenchmarkRunStatus.COMPLETED,
    ]
    assert all(run.persisted for run in runs)


def test_stream_measurements_keep_sampling_retry_and_title_signals_distinct() -> None:
    captured_snapshots: list[object] = []
    fake_case = SimpleNamespace(
        capture_source_state=lambda **arguments: captured_snapshots.append(arguments["snapshot"]) or object()
    )
    measurements = runner._StreamMeasurements()  # noqa: SLF001 - compact event fold proof
    snapshot = object()

    measurements.observe(
        SimpleNamespace(kind="snapshot", pending_message_id=None, snapshot=snapshot),
        case=fake_case,
        dataset_service=object(),
    )
    measurements.observe(
        SimpleNamespace(kind="connection", pending_message_id="pending-1", snapshot=None),
        case=fake_case,
        dataset_service=object(),
    )
    measurements.observe(
        SimpleNamespace(kind="title", pending_message_id="pending-2", snapshot=None),
        case=fake_case,
        dataset_service=object(),
    )

    assert measurements.pending_message_ids == {"pending-1", "pending-2"}
    assert measurements.provider_retry_count == 1
    assert measurements.title_event_count == 1
    assert captured_snapshots == [snapshot]


def test_missing_usage_stays_null_and_valid_usage_is_aggregated() -> None:
    no_usage_harness = SimpleNamespace(project_chatbot_events=lambda _snapshot: [])
    usage_harness = SimpleNamespace(
        project_chatbot_events=lambda _snapshot: [
            SimpleNamespace(
                kind="usage",
                usage_payload={
                    "request_count": 2,
                    "input_tokens": 10,
                    "cached_input_tokens": 3,
                    "output_tokens": 4,
                    "total_tokens": 14,
                },
            )
        ]
    )

    assert runner._usage_metrics(no_usage_harness, object()) == (None, None)  # noqa: SLF001
    count, usage = runner._usage_metrics(usage_harness, object())  # noqa: SLF001
    assert count == 2
    assert usage is not None
    assert usage.to_payload() == {
        "input_tokens": 10,
        "cached_input_tokens": 3,
        "output_tokens": 4,
        "total_tokens": 14,
    }


def test_result_write_failure_does_not_claim_persistence(tmp_path: Path, monkeypatch) -> None:
    result = AgentHarnessBenchmarkResult(
        case_id="test.case",
        run_id="run",
        provider_model="benchmark/one",
        run_status=BenchmarkRunStatus.COMPLETED,
        metrics=BenchmarkMetrics(),
        identity=BenchmarkIdentity(),
    )
    monkeypatch.setattr(runner, "_write_result", lambda *_args: (_ for _ in ()).throw(OSError("blocked")))

    runs = runner._persist_all(tmp_path, [result])  # noqa: SLF001 - persistence failure branch

    assert len(runs) == 1
    assert runs[0].persisted is False
