"""Strict loader for versioned, case-independent Judge calibration packets.

The manifest owns only hand-labelled calibration examples and their bounded
calibration intent.  Live benchmark modules remain authoritative for rubric
objects, which are resolved by symbol and incorporated into the suite hash.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import re
from typing import Any

from .contracts import JudgeInput, JudgeRubric, SemanticVerdict
from .judge_calibration import JudgeCalibrationError


CALIBRATION_MANIFEST_KIND = "xenix.agent_harness.judge_calibration_manifest"
CALIBRATION_MANIFEST_SCHEMA_VERSION = 1
_MAX_MANIFEST_BYTES = 262_144
_MAX_MANIFEST_SUITES = 32
_MAX_REFERENCE_CHARS = 256
_MAX_ID_CHARS = 128
_MAX_PACKET_COUNT = 4
_MAX_FACT_COUNT = 12
_MAX_EVIDENCE_COUNT = 48
_MAX_TEXT_CHARS = 512
_CASE_MODULE_PATTERN = re.compile(r"benchmarks\.agent_harness\.test_[A-Za-z0-9_]+")
_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
_CALIBRATION_VERDICTS = frozenset(
    {
        SemanticVerdict.PASS,
        SemanticVerdict.PARTIAL,
        SemanticVerdict.FAIL,
        SemanticVerdict.INCONCLUSIVE,
    }
)


@dataclass(frozen=True)
class CalibrationManifestPacket:
    fixture_id: str
    expected_verdict: SemanticVerdict
    judge_input: JudgeInput


@dataclass(frozen=True)
class LoadedCalibrationManifestSuite:
    """One selected suite with a stable, path-free report identity."""

    suite_symbol: str
    manifest_id: str
    suite_id: str
    packets: tuple[CalibrationManifestPacket, ...]


def load_calibration_manifest_suite(
    path: Path,
    *,
    suite_id: str,
) -> LoadedCalibrationManifestSuite:
    """Load one exact-rubric suite from a bounded calibration manifest."""

    payload = _load_manifest_payload(path)
    manifest_id = _bounded_id(
        payload.get("manifest_id"),
        "calibration_manifest_identity_invalid",
    )
    suites = payload.get("suites")
    if not isinstance(suites, list) or not 0 < len(suites) <= _MAX_MANIFEST_SUITES:
        raise JudgeCalibrationError("calibration_manifest_suites_invalid")
    requested_suite_id = _bounded_id(
        suite_id,
        "calibration_manifest_suite_id_invalid",
    )
    parsed: dict[str, tuple[CalibrationManifestPacket, ...]] = {}
    for raw_suite in suites:
        current_id, packets = _parse_suite(raw_suite)
        if current_id in parsed:
            raise JudgeCalibrationError("calibration_manifest_suite_id_duplicate")
        parsed[current_id] = packets
    packets = parsed.get(requested_suite_id)
    if packets is None:
        raise JudgeCalibrationError("calibration_manifest_suite_not_found")
    return LoadedCalibrationManifestSuite(
        suite_symbol=f"manifest:{manifest_id}:{requested_suite_id}",
        manifest_id=manifest_id,
        suite_id=requested_suite_id,
        packets=packets,
    )


def _load_manifest_payload(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > _MAX_MANIFEST_BYTES:
            raise JudgeCalibrationError("calibration_manifest_too_large")
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except JudgeCalibrationError:
        raise
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise JudgeCalibrationError("calibration_manifest_json_invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "manifest_kind",
        "schema_version",
        "manifest_id",
        "suites",
    }:
        raise JudgeCalibrationError("calibration_manifest_shape_invalid")
    if payload["manifest_kind"] != CALIBRATION_MANIFEST_KIND:
        raise JudgeCalibrationError("calibration_manifest_kind_invalid")
    schema_version = payload["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != CALIBRATION_MANIFEST_SCHEMA_VERSION
    ):
        raise JudgeCalibrationError("calibration_manifest_version_invalid")
    return payload


def _parse_suite(value: object) -> tuple[str, tuple[CalibrationManifestPacket, ...]]:
    if not isinstance(value, dict) or set(value) != {
        "suite_id",
        "rubric_symbol",
        "task_intent",
        "facts",
        "packets",
    }:
        raise JudgeCalibrationError("calibration_manifest_suite_shape_invalid")
    suite_id = _bounded_id(value["suite_id"], "calibration_manifest_suite_id_invalid")
    rubric = _resolve_symbol(value["rubric_symbol"], expected_type=JudgeRubric)
    if suite_id != rubric.rubric_id:
        raise JudgeCalibrationError("calibration_manifest_rubric_identity_mismatch")
    task_intent = _bounded_text(
        value["task_intent"],
        "calibration_manifest_task_intent_invalid",
    )
    facts = _bounded_strings(
        value["facts"],
        code="calibration_manifest_facts_invalid",
        maximum_items=_MAX_FACT_COUNT,
        allow_empty=False,
    )
    raw_packets = value["packets"]
    if not isinstance(raw_packets, list) or not 0 < len(raw_packets) <= _MAX_PACKET_COUNT:
        raise JudgeCalibrationError("calibration_manifest_packets_invalid")
    packets = tuple(
        _parse_packet(
            packet,
            rubric=rubric,
            task_intent=task_intent,
            facts=facts,
        )
        for packet in raw_packets
    )
    if len({packet.fixture_id for packet in packets}) != len(packets):
        raise JudgeCalibrationError("calibration_manifest_fixture_id_duplicate")
    return suite_id, packets


def _parse_packet(
    value: object,
    *,
    rubric: JudgeRubric,
    task_intent: str,
    facts: tuple[str, ...],
) -> CalibrationManifestPacket:
    if not isinstance(value, dict) or set(value) != {
        "fixture_id",
        "expected_verdict",
        "artifact_evidence",
    }:
        raise JudgeCalibrationError("calibration_manifest_packet_shape_invalid")
    fixture_id = _bounded_id(
        value["fixture_id"],
        "calibration_manifest_fixture_id_invalid",
        maximum=_MAX_ID_CHARS,
    )
    expected_raw = value["expected_verdict"]
    try:
        expected = SemanticVerdict(expected_raw)
    except (TypeError, ValueError) as exc:
        raise JudgeCalibrationError("calibration_manifest_verdict_invalid") from exc
    if expected not in _CALIBRATION_VERDICTS:
        raise JudgeCalibrationError("calibration_manifest_verdict_invalid")
    evidence = _bounded_strings(
        value["artifact_evidence"],
        code="calibration_manifest_evidence_invalid",
        maximum_items=_MAX_EVIDENCE_COUNT,
        allow_empty=expected is SemanticVerdict.INCONCLUSIVE,
    )
    if expected is SemanticVerdict.INCONCLUSIVE and evidence:
        raise JudgeCalibrationError("calibration_manifest_inconclusive_evidence_invalid")
    try:
        judge_input = JudgeInput(
            rubric=rubric,
            task_intent=task_intent,
            facts=facts,
            artifact_evidence=evidence,
        )
    except ValueError as exc:
        raise JudgeCalibrationError("calibration_manifest_judge_input_invalid") from exc
    return CalibrationManifestPacket(
        fixture_id=fixture_id,
        expected_verdict=expected,
        judge_input=judge_input,
    )


def _resolve_symbol(reference: object, *, expected_type: type[Any]) -> Any:
    if not isinstance(reference, str) or len(reference) > _MAX_REFERENCE_CHARS:
        raise JudgeCalibrationError("calibration_manifest_symbol_invalid")
    module_name, separator, symbol_name = reference.partition(":")
    if (
        not separator
        or not _CASE_MODULE_PATTERN.fullmatch(module_name)
        or not symbol_name.isidentifier()
    ):
        raise JudgeCalibrationError("calibration_manifest_symbol_invalid")
    try:
        value = getattr(importlib.import_module(module_name), symbol_name)
    except Exception as exc:
        raise JudgeCalibrationError("calibration_manifest_symbol_invalid") from exc
    if not isinstance(value, expected_type):
        raise JudgeCalibrationError("calibration_manifest_symbol_type_invalid")
    return value


def _bounded_id(value: object, code: str, *, maximum: int = _MAX_ID_CHARS) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if (
        not normalized
        or len(normalized) > maximum
        or _ID_PATTERN.fullmatch(normalized) is None
    ):
        raise JudgeCalibrationError(code)
    return normalized


def _bounded_text(value: object, code: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized or len(normalized) > _MAX_TEXT_CHARS:
        raise JudgeCalibrationError(code)
    return normalized


def _bounded_strings(
    value: object,
    *,
    code: str,
    maximum_items: int,
    allow_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise JudgeCalibrationError(code)
    if not value and not allow_empty:
        raise JudgeCalibrationError(code)
    strings = tuple(value)
    if any(
        not isinstance(item, str)
        or not item.strip()
        or len(item) > _MAX_TEXT_CHARS
        for item in strings
    ):
        raise JudgeCalibrationError(code)
    return strings


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise JudgeCalibrationError("calibration_manifest_json_invalid")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise JudgeCalibrationError("calibration_manifest_json_invalid")
