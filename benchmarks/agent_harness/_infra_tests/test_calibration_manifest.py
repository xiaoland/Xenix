from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.agent_harness._infra.calibration_manifest import (
    load_calibration_manifest_suite,
)
from benchmarks.agent_harness._infra.contracts import SemanticVerdict
from benchmarks.agent_harness._infra.judge_calibration import JudgeCalibrationError
from benchmarks.agent_harness.test_ml_cluster_selection import (
    CLUSTER_SELECTION_RUBRIC,
)
from benchmarks.agent_harness.test_ml_forecast_validation import (
    FORECAST_VALIDATION_RUBRIC,
)
from benchmarks.agent_harness.test_ml_recommendation_ranking import (
    RECOMMENDATION_RANKING_RUBRIC,
)
from benchmarks.agent_harness.test_ml_text_grouped_classification import (
    TEXT_CLASSIFICATION_RUBRIC,
)
from benchmarks.agent_harness.test_ml_text_topic_discovery import (
    TOPIC_DISCOVERY_RUBRIC,
)


_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "ml_formal_judge_calibrations.json"
)
_EXPECTED_RUBRICS = (
    CLUSTER_SELECTION_RUBRIC,
    FORECAST_VALIDATION_RUBRIC,
    RECOMMENDATION_RANKING_RUBRIC,
    TEXT_CLASSIFICATION_RUBRIC,
    TOPIC_DISCOVERY_RUBRIC,
)


def test_formal_manifest_resolves_each_authoritative_rubric() -> None:
    for rubric in _EXPECTED_RUBRICS:
        suite_id = rubric.rubric_id
        suite = load_calibration_manifest_suite(_MANIFEST_PATH, suite_id=suite_id)

        assert suite.suite_id == rubric.rubric_id
        assert suite.suite_symbol == (
            f"manifest:ml-formal-judge-calibrations-v1:{rubric.rubric_id}"
        )
        assert len(suite.packets) == 4
        assert {packet.expected_verdict for packet in suite.packets} == {
            SemanticVerdict.PASS,
            SemanticVerdict.PARTIAL,
            SemanticVerdict.FAIL,
            SemanticVerdict.INCONCLUSIVE,
        }
        assert all(packet.judge_input.rubric is rubric for packet in suite.packets)
        assert all(packet.judge_input.task_intent for packet in suite.packets)


def test_manifest_rejects_rubric_identity_drift(tmp_path: Path) -> None:
    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["suites"][0]["suite_id"] = "drifted.rubric.v1"
    manifest = tmp_path / "drifted.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        JudgeCalibrationError,
        match="calibration_manifest_rubric_identity_mismatch",
    ):
        load_calibration_manifest_suite(manifest, suite_id="drifted.rubric.v1")


def test_manifest_rejects_non_case_symbol_before_loading_it(tmp_path: Path) -> None:
    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    suite_id = payload["suites"][0]["suite_id"]
    payload["suites"][0]["rubric_symbol"] = "pathlib:Path"
    manifest = tmp_path / "unsafe-symbol.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        JudgeCalibrationError,
        match="calibration_manifest_symbol_invalid",
    ):
        load_calibration_manifest_suite(manifest, suite_id=suite_id)
