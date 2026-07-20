"""Outcome oracle for the real April dine-in sales cleaning benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

import polars as pl

from xenix.services.agent import SourceAttachmentInput, SubmitUserTurnInput
from xenix.services.llm.messages import DatasetBlock, blocks_from_payload
from xenix.services.tabular import load_tabular_frame

from .contracts import OutcomeCheck


CASE_ID = "cleaning.april_dine_in_sales"
EXPECTED_FILE_SIZE = 116_459_191
EXPECTED_SHA256 = "6B902DE50277E727FE936FFC4FE072B4D8B1C3D60A7D85413E114B72C4140E31"
EXPECTED_SHAPE = (485_790, 50)
_DATASET_ID_LINE = re.compile(r"^dataset_id:\s*([A-Za-z0-9_-]+)\s*$", re.MULTILINE)


class BenchmarkInputError(ValueError):
    """A safe, stable case/setup problem suitable for a result report."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AprilSourceState:
    external_sha256: str
    source_dataset_ids: tuple[str, ...]
    registered_dataset_sha256: dict[str, str]


@dataclass(frozen=True)
class AprilCaseAssessment:
    checks: tuple[OutcomeCheck, ...]
    terminal_shape: tuple[int, int] | None


class AprilDineInSalesCleaningCase:
    """One outcome-first cleaning case; it does not prescribe Tool behavior."""

    case_id = CASE_ID

    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def validate_input(self) -> str:
        if not self.source_path.is_file():
            raise BenchmarkInputError("missing_fixture")
        if self.source_path.stat().st_size != EXPECTED_FILE_SIZE:
            raise BenchmarkInputError("fixture_size_mismatch")
        digest = _sha256_file(self.source_path)
        if digest != EXPECTED_SHA256:
            raise BenchmarkInputError("fixture_hash_mismatch")
        return digest

    def build_submission(self, *, thread_id: str, fq_model_key: str) -> SubmitUserTurnInput:
        return SubmitUserTurnInput(
            thread_id=thread_id,
            text="清洗",
            source_attachments=[SourceAttachmentInput(file_path=str(self.source_path.resolve()))],
            fq_model_key=fq_model_key,
        )

    def capture_source_state(self, *, snapshot: Any, dataset_service: Any) -> AprilSourceState:
        source_dataset_ids = _dataset_ids_from_user_messages(snapshot)
        registered_hashes: dict[str, str] = {}
        for dataset_id in source_dataset_ids:
            dataset = dataset_service.get_dataset(dataset_id)
            source_path = Path(dataset.source_path)
            if not source_path.is_file():
                raise BenchmarkInputError("registered_source_unreadable")
            registered_hashes[dataset_id] = _sha256_file(source_path)
        return AprilSourceState(
            external_sha256=_sha256_file(self.source_path),
            source_dataset_ids=tuple(source_dataset_ids),
            registered_dataset_sha256=registered_hashes,
        )

    def assess(
        self,
        *,
        snapshot: Any | None,
        dataset_service: Any,
        source_state: AprilSourceState | None,
        run_dataset_ids: set[str],
        runtime_home: Path,
        settings_unchanged: bool,
    ) -> AprilCaseAssessment:
        if snapshot is None or source_state is None or not source_state.source_dataset_ids:
            checks = (
                OutcomeCheck("canonical_completion", False, "no_canonical_snapshot"),
                OutcomeCheck("terminal_output_resolved", False, "no_canonical_snapshot"),
                OutcomeCheck("header_promoted", False, "no_terminal_dataset"),
                OutcomeCheck("report_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("header_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("exact_duplicates_removed", False, "no_terminal_dataset"),
                OutcomeCheck("expected_shape", False, "no_terminal_dataset"),
                OutcomeCheck("business_rows_preserved", False, "no_terminal_dataset"),
                OutcomeCheck("source_unchanged", False, "source_state_unavailable"),
                OutcomeCheck("state_isolated", False, "source_state_unavailable"),
            )
            return AprilCaseAssessment(checks=checks, terminal_shape=None)

        terminal = self._resolve_terminal_dataset(
            snapshot=snapshot,
            dataset_service=dataset_service,
            source_dataset_ids=set(source_state.source_dataset_ids),
            run_dataset_ids=run_dataset_ids,
        )
        canonical_complete = _canonical_completion(snapshot)
        source_unchanged = self._source_unchanged(source_state, dataset_service)
        state_isolated = self._state_isolated(
            dataset_service=dataset_service,
            runtime_home=runtime_home,
            settings_unchanged=settings_unchanged,
        )
        if terminal is None:
            checks = (
                OutcomeCheck("canonical_completion", canonical_complete, _completion_summary(canonical_complete)),
                OutcomeCheck("terminal_output_resolved", False, "no_readable_run_output_reference"),
                OutcomeCheck("header_promoted", False, "no_terminal_dataset"),
                OutcomeCheck("report_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("header_row_removed", False, "no_terminal_dataset"),
                OutcomeCheck("exact_duplicates_removed", False, "no_terminal_dataset"),
                OutcomeCheck("expected_shape", False, "no_terminal_dataset"),
                OutcomeCheck("business_rows_preserved", False, "no_terminal_dataset"),
                OutcomeCheck("source_unchanged", source_unchanged, _source_summary(source_unchanged)),
                OutcomeCheck("state_isolated", state_isolated, _isolation_summary(state_isolated)),
            )
            return AprilCaseAssessment(checks=checks, terminal_shape=None)

        terminal_dataset, output_frame = terminal
        source_dataset = dataset_service.get_dataset(source_state.source_dataset_ids[0])
        source_frame = _load_dataset_frame(source_dataset)
        shape = (int(output_frame.height), int(output_frame.width))
        table_checks = _cleaning_checks(source_frame=source_frame, output_frame=output_frame)
        checks = (
            OutcomeCheck("canonical_completion", canonical_complete, _completion_summary(canonical_complete)),
            OutcomeCheck("terminal_output_resolved", True, "readable_run_output_reference"),
            *table_checks,
            OutcomeCheck("source_unchanged", source_unchanged, _source_summary(source_unchanged)),
            OutcomeCheck("state_isolated", state_isolated, _isolation_summary(state_isolated)),
        )
        del terminal_dataset
        return AprilCaseAssessment(checks=checks, terminal_shape=shape)

    @staticmethod
    def _resolve_terminal_dataset(
        *,
        snapshot: Any,
        dataset_service: Any,
        source_dataset_ids: set[str],
        run_dataset_ids: set[str],
    ) -> tuple[Any, pl.DataFrame] | None:
        for message in reversed(list(getattr(snapshot, "messages", []))):
            if _enum_value(getattr(message, "kind", None)) != "tool_result":
                continue
            if _enum_value(getattr(message, "result_status", None)) != "succeeded":
                continue
            for dataset_id in _result_dataset_ids(getattr(message, "value_payload", None)):
                if dataset_id in source_dataset_ids or dataset_id not in run_dataset_ids:
                    continue
                try:
                    dataset = dataset_service.get_dataset(dataset_id)
                    frame = _load_dataset_frame(dataset)
                except Exception:
                    continue
                return dataset, frame
        return None

    def _source_unchanged(self, source_state: AprilSourceState, dataset_service: Any) -> bool:
        if _sha256_file(self.source_path) != source_state.external_sha256:
            return False
        try:
            return all(
                _sha256_file(Path(dataset_service.get_dataset(dataset_id).source_path)) == digest
                for dataset_id, digest in source_state.registered_dataset_sha256.items()
            )
        except Exception:
            return False

    @staticmethod
    def _state_isolated(*, dataset_service: Any, runtime_home: Path, settings_unchanged: bool) -> bool:
        if not settings_unchanged:
            return False
        try:
            root = runtime_home.resolve()
            return all(
                _is_within(Path(dataset.source_path), root)
                for dataset in dataset_service.list_datasets()
            )
        except Exception:
            return False


def _cleaning_checks(*, source_frame: pl.DataFrame, output_frame: pl.DataFrame) -> tuple[OutcomeCheck, ...]:
    if source_frame.height < 2 or source_frame.width != output_frame.width:
        return (
            OutcomeCheck("header_promoted", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("report_row_removed", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("header_row_removed", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("exact_duplicates_removed", False, "incompatible_source_or_output_schema"),
            OutcomeCheck("expected_shape", False, "unexpected_terminal_shape"),
            OutcomeCheck("business_rows_preserved", False, "incompatible_source_or_output_schema"),
        )

    expected_headers = tuple(_cell_text(value) for value in source_frame.row(1))
    header_promoted = tuple(output_frame.columns) == expected_headers
    output_hashes = _row_hashes(output_frame)
    source_business_hashes = _row_hashes(source_frame.slice(2))
    report_row_hash = _row_hashes(source_frame.slice(0, 1))[0]
    header_row_hash = _row_hashes(source_frame.slice(1, 1))[0]
    output_hash_set = set(output_hashes.to_list())
    duplicates_removed = output_hashes.n_unique() == output_frame.height
    expected_shape = (int(output_frame.height), int(output_frame.width)) == EXPECTED_SHAPE
    business_rows_preserved = source_business_hashes.unique().sort().equals(output_hashes.unique().sort())
    return (
        OutcomeCheck("header_promoted", header_promoted, "expected_headers" if header_promoted else "headers_not_promoted"),
        OutcomeCheck("report_row_removed", report_row_hash not in output_hash_set, "report_row_absent" if report_row_hash not in output_hash_set else "report_row_retained"),
        OutcomeCheck("header_row_removed", header_row_hash not in output_hash_set, "header_row_absent" if header_row_hash not in output_hash_set else "header_row_retained"),
        OutcomeCheck("exact_duplicates_removed", duplicates_removed, "no_exact_duplicates" if duplicates_removed else "exact_duplicates_retained"),
        OutcomeCheck("expected_shape", expected_shape, "expected_terminal_shape" if expected_shape else "unexpected_terminal_shape"),
        OutcomeCheck("business_rows_preserved", business_rows_preserved, "business_rows_match" if business_rows_preserved else "business_rows_differ"),
    )


def _row_hashes(frame: pl.DataFrame) -> pl.Series:
    normalized = frame.select(
        [_normalized_value_expression(column).alias(column) for column in frame.columns]
    )
    return normalized.hash_rows()


def _normalized_value_expression(column: str) -> pl.Expr:
    text = pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars()
    return pl.when(pl.col(column).is_null() | text.is_in(["", "--"])).then(None).otherwise(text)


def _dataset_ids_from_user_messages(snapshot: Any) -> list[str]:
    dataset_ids: list[str] = []
    for message in getattr(snapshot, "messages", []):
        if _enum_value(getattr(message, "kind", None)) != "user":
            continue
        payload = getattr(message, "content_payload", None)
        for block in blocks_from_payload(payload if isinstance(payload, dict) else None):
            if isinstance(block, DatasetBlock) and block.dataset_id not in dataset_ids:
                dataset_ids.append(block.dataset_id)
    return dataset_ids


def _result_dataset_ids(value: Any) -> tuple[str, ...]:
    candidates: list[str] = []
    if isinstance(value, dict):
        direct = value.get("dataset_id")
        if isinstance(direct, str) and direct.strip():
            candidates.append(direct.strip())
        multiple = value.get("dataset_ids")
        if isinstance(multiple, list):
            candidates.extend(item.strip() for item in multiple if isinstance(item, str) and item.strip())
    elif isinstance(value, str):
        metadata = value.split("\n\n", 1)[0]
        candidates.extend(match.group(1) for match in _DATASET_ID_LINE.finditer(metadata))
    return tuple(dict.fromkeys(candidates))


def _load_dataset_frame(dataset: Any) -> pl.DataFrame:
    return load_tabular_frame(Path(dataset.source_path), dataset.source_format)


def _canonical_completion(snapshot: Any) -> bool:
    messages = list(getattr(snapshot, "messages", []))
    if not messages or any(_enum_value(getattr(message, "kind", None)) == "pending_llm_sampling" for message in messages):
        return False
    terminal = messages[-1]
    return _enum_value(getattr(terminal, "kind", None)) == "assistant" and not bool(
        getattr(terminal, "refusal", None)
    )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _cell_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _completion_summary(passed: bool) -> str:
    return "canonical_assistant_completion" if passed else "not_a_terminal_assistant_completion"


def _source_summary(passed: bool) -> str:
    return "external_and_registered_source_unchanged" if passed else "source_changed_or_unreadable"


def _isolation_summary(passed: bool) -> str:
    return "state_confined_to_cell_runtime" if passed else "state_or_settings_escaped_cell_runtime"
