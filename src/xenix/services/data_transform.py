from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import duckdb
import pandas as pd
from pydantic import Field
from sqlmodel import SQLModel

from ..config import AppPaths
from ..exceptions import ValidationError
from ..observability import record_counter, record_histogram, start_span
from .dataset_inspection import detect_source_format
from .storage.models import DatasetSourceFormat
from .tabular import load_pandas_frame_with_schema, load_tabular_frame, resolve_tabular_schema


_MAX_SQL_LENGTH = 20_000
_MAX_QUERY_LIMIT = 200
_DEFAULT_QUERY_LIMIT = 50
_ALIAS_RESERVED_WORDS = {
    "all",
    "and",
    "as",
    "by",
    "case",
    "delete",
    "from",
    "group",
    "insert",
    "join",
    "limit",
    "on",
    "or",
    "order",
    "select",
    "set",
    "update",
    "where",
    "with",
}
_DISALLOWED_KEYWORDS = {
    "alter",
    "attach",
    "call",
    "checkpoint",
    "copy",
    "create",
    "delete",
    "detach",
    "drop",
    "export",
    "force",
    "import",
    "insert",
    "install",
    "load",
    "merge",
    "pragma",
    "reset",
    "set",
    "truncate",
    "update",
    "vacuum",
}
_DISALLOWED_FUNCTIONS = {
    "arrow_scan",
    "delta_scan",
    "excel_scan",
    "glob",
    "iceberg_scan",
    "json_scan",
    "mysql_scan",
    "parquet_scan",
    "postgres_scan",
    "read_blob",
    "read_csv",
    "read_csv_auto",
    "read_json",
    "read_json_auto",
    "read_ndjson",
    "read_parquet",
    "read_text",
    "read_xlsx",
    "sqlite_scan",
}


class DatasetSqlBinding(SQLModel):
    alias: str
    dataset_id: str
    source_path: str


class DataQueryInput(SQLModel):
    bindings: list[DatasetSqlBinding]
    sql: str
    limit: int = _DEFAULT_QUERY_LIMIT


class DataTransformInput(SQLModel):
    bindings: list[DatasetSqlBinding]
    sql: str
    name: str


class DataQueryResult(SQLModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[dict[str, str]] = Field(default_factory=list)
    returned_row_count: int = 0
    limit: int = _DEFAULT_QUERY_LIMIT
    truncated: bool = False
    validation_summary: dict[str, Any] = Field(default_factory=dict)


class DataTransformResult(SQLModel):
    output_path: str
    row_count: int = 0
    columns: list[dict[str, str]] = Field(default_factory=list)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    transform_report: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class _SqlToken:
    kind: str
    value: str

    @property
    def lower(self) -> str:
        return self.value.lower()


class DuckDbSqlValidator:
    def validate(self, sql: str, bindings: list[DatasetSqlBinding]) -> dict[str, Any]:
        normalized_sql = sql.strip()
        if not normalized_sql:
            raise ValidationError("SQL cannot be empty.")
        if len(normalized_sql) > _MAX_SQL_LENGTH:
            raise ValidationError(f"SQL cannot exceed {_MAX_SQL_LENGTH} characters.")
        aliases = self._validate_aliases(bindings)
        tokens = self._tokens(normalized_sql)
        significant = [token for token in tokens if token.kind in {"word", "identifier", "string", "symbol"}]
        word_tokens = [token for token in significant if token.kind == "word"]
        if not word_tokens:
            raise ValidationError("SQL must contain a SELECT or WITH statement.")
        first_word = word_tokens[0].lower
        if first_word in _DISALLOWED_KEYWORDS:
            raise ValidationError(f"SQL contains unsupported statement keyword: {first_word}.")
        if first_word not in {"select", "with"}:
            raise ValidationError("SQL must start with SELECT or WITH.")

        semicolon_indexes = [index for index, token in enumerate(significant) if token.value == ";"]
        if semicolon_indexes:
            if len(semicolon_indexes) > 1 or semicolon_indexes[0] != len(significant) - 1:
                raise ValidationError("SQL must be a single statement.")

        disallowed = sorted({token.lower for token in word_tokens if token.lower in _DISALLOWED_KEYWORDS})
        if disallowed:
            raise ValidationError(f"SQL contains unsupported statement keyword: {disallowed[0]}.")

        for index, token in enumerate(significant):
            if token.kind == "word" and token.lower in _DISALLOWED_FUNCTIONS:
                next_token = significant[index + 1] if index + 1 < len(significant) else None
                if next_token is None or next_token.value == "(":
                    raise ValidationError(f"SQL cannot call DuckDB file scan function '{token.value}'.")
            if token.kind == "string" and self._previous_word(significant, index) in {"from", "join"}:
                raise ValidationError("SQL cannot read direct file paths; use registered dataset bindings.")

        referenced_aliases = sorted(
            {
                token.lower
                for token in word_tokens
                if token.lower in {alias.lower() for alias in aliases}
            }
        )
        if not referenced_aliases:
            raise ValidationError("SQL must reference at least one registered dataset binding.")

        return {
            "statement": first_word,
            "read_only": True,
            "single_statement": True,
            "bindings": aliases,
            "referenced_bindings": referenced_aliases,
        }

    def normalize_sql(self, sql: str) -> str:
        normalized = sql.strip()
        while normalized.endswith(";"):
            normalized = normalized[:-1].rstrip()
        return normalized

    def normalize_alias(self, alias: str) -> str:
        return self._normalize_alias(alias)

    def _validate_aliases(self, bindings: list[DatasetSqlBinding]) -> list[str]:
        if not bindings:
            raise ValidationError("At least one dataset binding is required.")
        aliases: list[str] = []
        seen: set[str] = set()
        for binding in bindings:
            alias = self._normalize_alias(binding.alias)
            lowered = alias.lower()
            if lowered in seen:
                raise ValidationError(f"Dataset binding alias '{alias}' is duplicated.")
            seen.add(lowered)
            aliases.append(alias)
        return aliases

    def _normalize_alias(self, alias: str) -> str:
        normalized = str(alias or "").strip()
        if not normalized:
            raise ValidationError("Dataset binding alias cannot be empty.")
        if normalized.lower() in _ALIAS_RESERVED_WORDS:
            raise ValidationError(f"Dataset binding alias '{normalized}' is reserved.")
        first = normalized[0]
        if not (first.isalpha() or first == "_"):
            raise ValidationError("Dataset binding alias must start with a letter or underscore.")
        if not all(char.isalnum() or char == "_" for char in normalized):
            raise ValidationError("Dataset binding alias must contain only letters, numbers, and underscores.")
        return normalized

    def _previous_word(self, tokens: list[_SqlToken], index: int) -> str | None:
        for token in reversed(tokens[:index]):
            if token.kind == "word":
                return token.lower
        return None

    def _tokens(self, sql: str) -> list[_SqlToken]:
        tokens: list[_SqlToken] = []
        index = 0
        while index < len(sql):
            char = sql[index]
            next_char = sql[index + 1] if index + 1 < len(sql) else ""
            if char.isspace():
                index += 1
                continue
            if char == "-" and next_char == "-":
                index = self._consume_line_comment(sql, index + 2)
                continue
            if char == "/" and next_char == "*":
                index = self._consume_block_comment(sql, index + 2)
                continue
            if char == "'":
                value, index = self._consume_quoted(sql, index, "'")
                tokens.append(_SqlToken("string", value))
                continue
            if char in {'"', "`"}:
                value, index = self._consume_quoted(sql, index, char)
                tokens.append(_SqlToken("identifier", value))
                continue
            if char.isalpha() or char == "_":
                start = index
                index += 1
                while index < len(sql) and (sql[index].isalnum() or sql[index] == "_"):
                    index += 1
                tokens.append(_SqlToken("word", sql[start:index]))
                continue
            if char in "();,.":
                tokens.append(_SqlToken("symbol", char))
            index += 1
        return tokens

    def _consume_line_comment(self, sql: str, index: int) -> int:
        while index < len(sql) and sql[index] not in {"\n", "\r"}:
            index += 1
        return index

    def _consume_block_comment(self, sql: str, index: int) -> int:
        while index + 1 < len(sql):
            if sql[index] == "*" and sql[index + 1] == "/":
                return index + 2
            index += 1
        raise ValidationError("SQL block comment is not closed.")

    def _consume_quoted(self, sql: str, index: int, quote: str) -> tuple[str, int]:
        start = index
        index += 1
        while index < len(sql):
            if sql[index] == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    index += 2
                    continue
                return sql[start : index + 1], index + 1
            index += 1
        raise ValidationError("SQL quoted value is not closed.")


class DataQueryTransformService:
    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths
        self._validator = DuckDbSqlValidator()

    def query(self, input_data: DataQueryInput) -> DataQueryResult:
        started_at = perf_counter()
        with start_span("data.query"):
            bindings = self._validate_bindings(input_data.bindings)
            validation_summary = self._validator.validate(input_data.sql, bindings)
            limit = self._normalize_limit(input_data.limit)
            sql = self._validator.normalize_sql(input_data.sql)
            with tempfile.TemporaryDirectory() as temp_dir:
                with duckdb.connect(database=":memory:") as connection:
                    self._register_bindings(connection, bindings, temp_dir=Path(temp_dir))
                    frame = connection.execute(
                        f"SELECT * FROM ({sql}) AS xenix_query_result LIMIT {limit + 1}"
                    ).fetchdf()
            truncated = int(len(frame.index)) > limit
            if truncated:
                frame = frame.head(limit)
            rows = self._records(frame)
            result = DataQueryResult(
                rows=rows,
                columns=self._columns(frame),
                returned_row_count=int(len(rows)),
                limit=limit,
                truncated=truncated,
                validation_summary=validation_summary,
            )
            self._record_operation("data.query", "succeeded", started_at)
            return result

    def transform(self, input_data: DataTransformInput) -> DataTransformResult:
        started_at = perf_counter()
        with start_span("data.transform"):
            bindings = self._validate_bindings(input_data.bindings)
            validation_summary = self._validator.validate(input_data.sql, bindings)
            name = input_data.name.strip()
            if not name:
                raise ValidationError("Transform output name cannot be empty.")
            sql = self._validator.normalize_sql(input_data.sql)
            with tempfile.TemporaryDirectory() as temp_dir:
                with duckdb.connect(database=":memory:") as connection:
                    self._register_bindings(connection, bindings, temp_dir=Path(temp_dir))
                    frame = connection.execute(sql).fetchdf()

            output_dir = self._paths.artifacts / "datasets" / "transformed"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{self._slug(name)}-{uuid4().hex[:12]}.csv"
            frame.to_csv(output_path, index=False)
            transform_report = {
                "row_count": int(len(frame.index)),
                "columns": self._columns(frame),
                "sql": sql,
                "bindings": [
                    {"alias": binding.alias, "dataset_id": binding.dataset_id}
                    for binding in bindings
                ],
                "validation_summary": validation_summary,
            }
            result = DataTransformResult(
                output_path=str(output_path.resolve()),
                row_count=int(len(frame.index)),
                columns=self._columns(frame),
                validation_summary=validation_summary,
                transform_report=transform_report,
            )
            self._record_operation("data.transform", "succeeded", started_at)
            return result

    def _record_operation(self, operation: str, status: str, started_at: float) -> None:
        attributes = {"data.operation": operation, "status": status}
        record_counter("xenix.data.operation.count", attributes=attributes)
        record_histogram(
            "xenix.data.operation.duration",
            (perf_counter() - started_at) * 1000,
            attributes=attributes,
            unit="ms",
        )

    def _register_bindings(self, connection, bindings: list[DatasetSqlBinding], *, temp_dir: Path) -> None:
        for binding in bindings:
            self._register_binding(connection, binding, temp_dir=temp_dir)

    def _register_binding(self, connection, binding: DatasetSqlBinding, *, temp_dir: Path) -> None:
        path = Path(binding.source_path).expanduser()
        source_format = detect_source_format(path)
        if source_format in {DatasetSourceFormat.XLSX, DatasetSourceFormat.XLS}:
            self._register_excel_binding(connection, binding, path, source_format, temp_dir=temp_dir)
            return
        frame = self._load_frame(path)
        connection.register(binding.alias, frame)

    def _register_excel_binding(
        self,
        connection,
        binding: DatasetSqlBinding,
        path: Path,
        source_format: DatasetSourceFormat,
        *,
        temp_dir: Path,
    ) -> None:
        frame = load_tabular_frame(path, source_format)
        schema = resolve_tabular_schema(frame.columns)
        frame = frame.rename(
            {
                original_name: column.tool_name
                for original_name, column in zip(frame.columns, schema.columns, strict=True)
            }
        )
        csv_path = temp_dir / f"{binding.alias}.csv"
        frame.write_csv(csv_path)
        connection.execute(
            f'CREATE TEMP TABLE "{binding.alias}" AS '
            "SELECT * FROM read_csv(?, header=true, all_varchar=true)",
            [str(csv_path)],
        )

    def _validate_bindings(self, bindings: list[DatasetSqlBinding]) -> list[DatasetSqlBinding]:
        normalized: list[DatasetSqlBinding] = []
        seen_aliases: set[str] = set()
        for binding in bindings:
            source_path = Path(binding.source_path).expanduser()
            if not source_path.is_absolute():
                raise ValidationError("Dataset source path must be absolute.")
            if not source_path.exists() or not source_path.is_file():
                raise ValidationError("Dataset source path must point to an existing file.")
            alias = self._validator.normalize_alias(binding.alias)
            lowered = alias.lower()
            if lowered in seen_aliases:
                raise ValidationError(f"Dataset binding alias '{alias}' is duplicated.")
            seen_aliases.add(lowered)
            normalized.append(
                DatasetSqlBinding(
                    alias=alias,
                    dataset_id=binding.dataset_id,
                    source_path=str(source_path.resolve()),
                )
            )
        if not normalized:
            raise ValidationError("At least one dataset binding is required.")
        return normalized

    def _load_frame(self, path: Path) -> pd.DataFrame:
        source_format = detect_source_format(path)
        if source_format is DatasetSourceFormat.UNKNOWN:
            raise ValidationError("Only .csv, .xlsx, and .xls dataset files are supported.")
        return load_pandas_frame_with_schema(path, source_format).frame

    def _normalize_limit(self, limit: int) -> int:
        try:
            normalized = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Query limit must be an integer.") from exc
        if normalized < 1 or normalized > _MAX_QUERY_LIMIT:
            raise ValidationError(f"Query limit must be between 1 and {_MAX_QUERY_LIMIT}.")
        return normalized

    def _columns(self, frame: pd.DataFrame) -> list[dict[str, str]]:
        return [{"name": str(column), "type": str(dtype)} for column, dtype in frame.dtypes.items()]

    def _records(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        cleaned = frame.astype(object).where(pd.notna(frame), None)
        return json.loads(cleaned.to_json(orient="records", date_format="iso"))

    def _slug(self, value: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return normalized or "dataset"
