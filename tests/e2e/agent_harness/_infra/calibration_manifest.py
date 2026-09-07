"""Load case-owned Judge rubrics and hand-labelled calibration examples."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from .contracts import JudgeInput, JudgeRubric, SemanticVerdict
from .judge_calibration import JudgeCalibrationError


@dataclass(frozen=True)
class CalibrationManifestPacket:
    fixture_id: str
    expected_verdict: SemanticVerdict
    judge_input: JudgeInput


@dataclass(frozen=True)
class LoadedCalibrationManifestSuite:
    suite_symbol: str
    manifest_id: str
    suite_id: str
    packets: tuple[CalibrationManifestPacket, ...]


class _ManifestFields(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Packet(_ManifestFields):
    fixture_id: str
    expected_verdict: Literal["pass", "partial", "fail", "inconclusive"]
    artifact_evidence: list[str]


class _Suite(_ManifestFields):
    suite_id: str
    rubric_symbol: str
    task_intent: str
    facts: list[str]
    packets: list[_Packet]


class _Manifest(_ManifestFields):
    manifest_kind: Literal["xenix.agent_harness.judge_calibration_manifest"]
    schema_version: Literal[1]
    manifest_id: str
    suites: list[_Suite]


def load_calibration_manifest_suite(path: Path, *, suite_id: str) -> LoadedCalibrationManifestSuite:
    """Resolve the selected rubric; other suites need not have importable symbols.

    Suite names are labels, independent of rubric identity. Paid packet limits
    and repetition topology belong to the calibration runner.
    """

    try:
        manifest = _Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise JudgeCalibrationError("calibration_manifest_invalid") from exc
    matches = [suite for suite in manifest.suites if suite.suite_id == suite_id]
    if len(matches) != 1:
        raise JudgeCalibrationError("calibration_manifest_suite_missing_or_ambiguous")
    suite = matches[0]
    rubric = _resolve_symbol(suite.rubric_symbol, expected_type=JudgeRubric)
    return LoadedCalibrationManifestSuite(
        suite_symbol=f"manifest:{manifest.manifest_id}:{suite.suite_id}",
        manifest_id=manifest.manifest_id,
        suite_id=suite.suite_id,
        packets=tuple(
            CalibrationManifestPacket(
                fixture_id=packet.fixture_id,
                expected_verdict=SemanticVerdict(packet.expected_verdict),
                judge_input=JudgeInput(
                    rubric=rubric,
                    task_intent=suite.task_intent,
                    facts=tuple(suite.facts),
                    artifact_evidence=tuple(packet.artifact_evidence),
                ),
            )
            for packet in suite.packets
        ),
    )


def _resolve_symbol(reference: str, *, expected_type: type[Any]) -> Any:
    module_name, separator, symbol_name = reference.partition(":")
    if (
        not separator
        or not module_name.startswith("tests.e2e.agent_harness.test_")
        or not all(part.isidentifier() for part in module_name.split("."))
        or not symbol_name.isidentifier()
    ):
        raise JudgeCalibrationError("calibration_manifest_symbol_invalid")
    try:
        value = getattr(importlib.import_module(module_name), symbol_name)
    except (ImportError, AttributeError) as exc:
        raise JudgeCalibrationError("calibration_manifest_symbol_invalid") from exc
    if not isinstance(value, expected_type):
        raise JudgeCalibrationError("calibration_manifest_symbol_type_invalid")
    return value
