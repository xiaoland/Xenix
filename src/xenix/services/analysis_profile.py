from __future__ import annotations

from datetime import date, datetime
import logging
import math
from pathlib import Path
import re
from time import perf_counter
from typing import Literal

try:
    import polars as pl
except Exception:  # pragma: no cover - depends on local runtime state
    pl = None
from pydantic import ConfigDict, Field
from sqlmodel import SQLModel

from ..exceptions import ValidationError
from ..observability import record_counter, record_histogram, start_span
from .dataset_inspection import detect_source_format
from .dataset_service import DatasetService
from .storage.models import DatasetSourceFormat
from .tabular import TabularRuntimeError, load_tabular_frame


DEFAULT_PROFILE_FIELD_LIMIT = 40
MAX_PROFILE_FIELD_LIMIT = 80
DEFAULT_NUMERIC_SUMMARY_LIMIT = 16
MAX_NUMERIC_SUMMARY_LIMIT = 32
DEFAULT_CORRELATION_COLUMN_LIMIT = 8
MAX_CORRELATION_COLUMN_LIMIT = 12
MAX_PROFILE_FIELD_NAME_CHARS = 160

_IDENTIFIER_NAME_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(id|identifier|key|uuid)(?:$|[^a-z0-9])|(?:编号|编码|代码)$",
    re.IGNORECASE,
)
LOGGER = logging.getLogger("xenix.services.analysis_profile")

ProfileScope = Literal["whole_dataset"]
ProfileLogicalType = Literal[
    "continuous_numeric",
    "binary",
    "categorical_text",
    "datetime",
    "identifier",
]


class _ProfileModel(SQLModel):
    model_config = ConfigDict(extra="forbid")


class ProfileDatasetInput(_ProfileModel):
    dataset_id: str = Field(min_length=1)
    field_limit: int = Field(
        default=DEFAULT_PROFILE_FIELD_LIMIT,
        ge=1,
        le=MAX_PROFILE_FIELD_LIMIT,
    )
    numeric_summary_limit: int = Field(
        default=DEFAULT_NUMERIC_SUMMARY_LIMIT,
        ge=1,
        le=MAX_NUMERIC_SUMMARY_LIMIT,
    )
    correlation_column_limit: int = Field(
        default=DEFAULT_CORRELATION_COLUMN_LIMIT,
        ge=2,
        le=MAX_CORRELATION_COLUMN_LIMIT,
    )


class ProfileBasicFacts(_ProfileModel):
    row_count: int
    column_count: int
    exact_duplicate_row_count: int


class ProfileFieldFact(_ProfileModel):
    index: int
    name: str
    name_truncated: bool = False
    logical_type: ProfileLogicalType
    missing_count: int
    missing_rate: float
    cardinality: int


class ProfileNumericSummary(_ProfileModel):
    field_index: int
    field_name: str
    non_missing_count: int
    mean: float | int | None = None
    standard_deviation: float | int | None = None
    minimum: float | int | None = None
    first_quartile: float | int | None = None
    median: float | int | None = None
    third_quartile: float | int | None = None
    maximum: float | int | None = None


class ProfileDatetimeRange(_ProfileModel):
    field_index: int
    field_name: str
    earliest: str | None = None
    latest: str | None = None
    span_days: int | None = None


class ProfileFieldReference(_ProfileModel):
    field_index: int
    field_name: str


class ProfileCorrelationFact(_ProfileModel):
    left_field_index: int
    right_field_index: int
    coefficient: float | int | None = None


class ProfileCorrelationProjection(_ProfileModel):
    eligible_field_count: int
    included_field_count: int
    truncated: bool
    fields: list[ProfileFieldReference] = Field(default_factory=list)
    facts: list[ProfileCorrelationFact] = Field(default_factory=list)


class ProfileSectionTruncation(_ProfileModel):
    total_count: int
    returned_count: int
    truncated: bool


class ProfileTruncation(_ProfileModel):
    fields: ProfileSectionTruncation
    numeric_summaries: ProfileSectionTruncation
    datetime_ranges: ProfileSectionTruncation


class ProfileDatasetResult(_ProfileModel):
    dataset_id: str
    scope: ProfileScope = "whole_dataset"
    basic: ProfileBasicFacts
    fields: list[ProfileFieldFact] = Field(default_factory=list)
    numeric_summaries: list[ProfileNumericSummary] = Field(default_factory=list)
    datetime_ranges: list[ProfileDatetimeRange] = Field(default_factory=list)
    correlations: ProfileCorrelationProjection
    truncation: ProfileTruncation


class AnalysisProfileService:
    def __init__(self, dataset_service: DatasetService) -> None:
        self._dataset_service = dataset_service

    def profile_dataset(self, input_data: ProfileDatasetInput) -> ProfileDatasetResult:
        started_at = perf_counter()
        with start_span("analysis.profile"):
            dataset_id = input_data.dataset_id.strip()
            if not dataset_id:
                raise ValidationError("Dataset id cannot be empty.")
            dataset = self._dataset_service.get_dataset(dataset_id)
            source_path = Path(dataset.source_path)
            source_format = dataset.source_format
            if source_format is DatasetSourceFormat.UNKNOWN:
                source_format = detect_source_format(source_path)
            frame = self._load_frame(
                dataset_id=dataset.id,
                source_path=source_path,
                source_format=source_format,
            )

            field_facts = self._field_facts(frame)
            returned_fields = field_facts[: input_data.field_limit]
            numeric_candidates = [
                field
                for field in field_facts
                if field.logical_type == "continuous_numeric"
            ]
            numeric_summaries = self._numeric_summaries(
                frame,
                numeric_candidates[: input_data.numeric_summary_limit],
            )
            datetime_candidates = [
                field for field in field_facts if field.logical_type == "datetime"
            ]
            returned_datetimes = datetime_candidates[: input_data.field_limit]
            datetime_ranges = self._datetime_ranges(frame, returned_datetimes)
            correlations = self._correlations(
                frame,
                numeric_candidates,
                input_data.correlation_column_limit,
            )
            result = ProfileDatasetResult(
                dataset_id=dataset.id,
                basic=ProfileBasicFacts(
                    row_count=int(frame.height),
                    column_count=int(frame.width),
                    exact_duplicate_row_count=int(frame.height - frame.unique().height),
                ),
                fields=returned_fields,
                numeric_summaries=numeric_summaries,
                datetime_ranges=datetime_ranges,
                correlations=correlations,
                truncation=ProfileTruncation(
                    fields=self._truncation(len(field_facts), len(returned_fields)),
                    numeric_summaries=self._truncation(
                        len(numeric_candidates),
                        len(numeric_summaries),
                    ),
                    datetime_ranges=self._truncation(
                        len(datetime_candidates),
                        len(datetime_ranges),
                    ),
                ),
            )
            self._record_operation(started_at)
            return result

    def _load_frame(
        self,
        *,
        dataset_id: str,
        source_path: Path,
        source_format: DatasetSourceFormat,
    ) -> pl.DataFrame:
        if source_format is DatasetSourceFormat.UNKNOWN:
            raise ValidationError("Registered dataset format is unsupported.")
        if pl is None:
            raise self._tabular_runtime_validation_error(
                dataset_id=dataset_id,
                source_format=source_format,
                exc=RuntimeError("Polars could not be imported."),
                phase="import",
            )
        try:
            frame = load_tabular_frame(source_path, source_format)
        except TabularRuntimeError as exc:
            LOGGER.exception("Dataset profile could not load the tabular runtime for dataset %s.", dataset_id)
            raise self._tabular_runtime_validation_error(
                dataset_id=dataset_id,
                source_format=source_format,
                exc=exc,
            ) from exc
        frame = frame.rename({column: str(column) for column in frame.columns})
        if frame.width == 0:
            raise ValidationError("Registered dataset must contain at least one column.")
        if frame.height == 0:
            raise ValidationError("Registered dataset must contain at least one data row.")
        return frame

    def _tabular_runtime_validation_error(
        self,
        *,
        dataset_id: str,
        source_format: DatasetSourceFormat,
        exc: Exception,
        phase: str | None = None,
    ) -> ValidationError:
        tabular_error_details = getattr(exc, "error_details", None)
        details = {
            "operation": "analysis.profile",
            "dataset_id": dataset_id,
            "source_format": source_format.value,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }
        if isinstance(tabular_error_details, dict) and tabular_error_details:
            details["tabular"] = tabular_error_details
        if phase:
            details["phase"] = phase
        return ValidationError(
            "Dataset analysis profile is unavailable because the tabular runtime could not load this dataset.",
            error_code="tabular_runtime_unavailable",
            error_details=details,
            repair_hints=[
                "Use data.query for a smaller schema query when you only need basic evidence.",
                "Repair the local tabular runtime, then retry.",
            ],
            retryable=True,
        )

    def _field_facts(self, frame: pl.DataFrame) -> list[ProfileFieldFact]:
        row_count = max(int(frame.height), 1)
        fields: list[ProfileFieldFact] = []
        for index, column in enumerate(frame.columns):
            series = frame[column]
            missing_count = self._missing_count(series)
            name, name_truncated = self._bounded_field_name(str(column))
            fields.append(
                ProfileFieldFact(
                    index=index,
                    name=name,
                    name_truncated=name_truncated,
                    logical_type=self._logical_type(str(column), series),
                    missing_count=missing_count,
                    missing_rate=float(self._number(missing_count / row_count) or 0.0),
                    cardinality=self._cardinality(series),
                )
            )
        return fields

    def _logical_type(self, column: str, series: pl.Series) -> ProfileLogicalType:
        if self._is_binary_column(series):
            return "binary"
        if self._is_datetime_column(series):
            return "datetime"
        if self._is_identifier_column(column):
            return "identifier"
        if series.dtype.is_numeric():
            return "continuous_numeric"
        return "categorical_text"

    def _is_identifier_column(self, column: str) -> bool:
        normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", column).casefold()
        return bool(_IDENTIFIER_NAME_PATTERN.search(normalized))

    def _is_binary_column(self, series: pl.Series) -> bool:
        if series.dtype == pl.Boolean:
            return True
        values = series.drop_nulls()
        if values.dtype.is_float():
            values = values.filter(~values.is_nan())
        unique_values = values.unique().to_list()
        if not unique_values or len(unique_values) > 2:
            return False
        normalized_values = {self._binary_value(value) for value in unique_values}
        return None not in normalized_values and normalized_values.issubset({0, 1})

    def _binary_value(self, value: object) -> int | None:
        try:
            if value == 0:
                return 0
            if value == 1:
                return 1
        except ValueError:
            return None
        return None

    def _is_datetime_column(self, series: pl.Series) -> bool:
        if series.dtype.is_temporal():
            return True
        if series.dtype.is_numeric():
            return False
        values = series.drop_nulls()
        if values.is_empty():
            return False
        parsed = self._to_datetime_series(values)
        valid_count = int(parsed.is_not_null().sum())
        return bool(valid_count / len(parsed) >= 0.8)

    def _numeric_summaries(
        self,
        frame: pl.DataFrame,
        fields: list[ProfileFieldFact],
    ) -> list[ProfileNumericSummary]:
        summaries: list[ProfileNumericSummary] = []
        for field in fields:
            series = self._numeric_series(frame[frame.columns[field.index]])
            summaries.append(
                ProfileNumericSummary(
                    field_index=field.index,
                    field_name=field.name,
                    non_missing_count=int(series.len()),
                    mean=self._number(series.mean() if not series.is_empty() else None),
                    standard_deviation=self._number(
                        series.std() if not series.is_empty() else None
                    ),
                    minimum=self._number(series.min() if not series.is_empty() else None),
                    first_quartile=self._number(
                        series.quantile(0.25) if not series.is_empty() else None
                    ),
                    median=self._number(series.median() if not series.is_empty() else None),
                    third_quartile=self._number(
                        series.quantile(0.75) if not series.is_empty() else None
                    ),
                    maximum=self._number(series.max() if not series.is_empty() else None),
                )
            )
        return summaries

    def _datetime_ranges(
        self,
        frame: pl.DataFrame,
        fields: list[ProfileFieldFact],
    ) -> list[ProfileDatetimeRange]:
        ranges: list[ProfileDatetimeRange] = []
        for field in fields:
            series = self._to_datetime_series(frame[frame.columns[field.index]]).drop_nulls()
            earliest = series.min() if not series.is_empty() else None
            latest = series.max() if not series.is_empty() else None
            span_days = None
            if earliest is not None and latest is not None:
                span_days = getattr(latest - earliest, "days", None)
            ranges.append(
                ProfileDatetimeRange(
                    field_index=field.index,
                    field_name=field.name,
                    earliest=self._display_datetime(earliest),
                    latest=self._display_datetime(latest),
                    span_days=span_days,
                )
            )
        return ranges

    def _correlations(
        self,
        frame: pl.DataFrame,
        numeric_fields: list[ProfileFieldFact],
        column_limit: int,
    ) -> ProfileCorrelationProjection:
        selected = numeric_fields[:column_limit]
        references = [
            ProfileFieldReference(field_index=field.index, field_name=field.name)
            for field in selected
        ]
        facts: list[ProfileCorrelationFact] = []
        if len(selected) >= 2:
            selected_columns = [frame.columns[field.index] for field in selected]
            matrix = frame.select(selected_columns).corr()
            for left_index in range(len(selected)):
                for right_index in range(left_index + 1, len(selected)):
                    facts.append(
                        ProfileCorrelationFact(
                            left_field_index=selected[left_index].index,
                            right_field_index=selected[right_index].index,
                            coefficient=self._number(matrix[left_index, right_index]),
                        )
                    )
        return ProfileCorrelationProjection(
            eligible_field_count=len(numeric_fields),
            included_field_count=len(selected),
            truncated=len(numeric_fields) > len(selected),
            fields=references,
            facts=facts,
        )

    def _missing_count(self, series: pl.Series) -> int:
        count = int(series.null_count())
        if series.dtype.is_float():
            count += int(series.is_nan().sum())
        return count

    def _cardinality(self, series: pl.Series) -> int:
        values = series.drop_nulls()
        if values.dtype.is_float():
            values = values.filter(~values.is_nan())
        return int(values.n_unique())

    def _numeric_series(self, series: pl.Series) -> pl.Series:
        values = series.cast(pl.Float64, strict=False).drop_nulls()
        return values.filter(~values.is_nan())

    def _to_datetime_series(self, series: pl.Series) -> pl.Series:
        if series.dtype == pl.Date:
            return series.cast(pl.Datetime)
        if series.dtype.is_temporal():
            return series
        values = series.cast(pl.String, strict=False)
        for datetime_format in (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            None,
        ):
            try:
                return values.str.to_datetime(format=datetime_format, strict=False)
            except pl.exceptions.ComputeError:
                continue
        return pl.Series(series.name, [None] * len(series), dtype=pl.Datetime)

    def _number(self, value: object, *, digits: int = 4) -> float | int | None:
        if value is None:
            return None
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        return round(number, digits)

    def _display_datetime(self, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()).isoformat()
        return str(value)

    def _bounded_field_name(self, value: str) -> tuple[str, bool]:
        if len(value) <= MAX_PROFILE_FIELD_NAME_CHARS:
            return value, False
        return value[: MAX_PROFILE_FIELD_NAME_CHARS - 1] + "…", True

    def _truncation(self, total_count: int, returned_count: int) -> ProfileSectionTruncation:
        return ProfileSectionTruncation(
            total_count=total_count,
            returned_count=returned_count,
            truncated=returned_count < total_count,
        )

    def _record_operation(self, started_at: float) -> None:
        attributes = {"analysis.operation": "analysis.profile", "status": "succeeded"}
        record_counter("xenix.analysis.operation.count", attributes=attributes)
        record_histogram(
            "xenix.analysis.operation.duration",
            (perf_counter() - started_at) * 1000,
            attributes=attributes,
            unit="ms",
        )
