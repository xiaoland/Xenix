# L3 Plan 01: Storage And Services

## 1. Dependencies

Files:

- `pyproject.toml`

Changes:

- add runtime dependencies:
  - `pandas`
  - `openpyxl`
  - `pydantic`
- do not add ML-specific libraries here for `#75`

Reasoning:

- `#75` needs file inspection for `.csv` / `.xlsx`
- `pydantic` is needed for typed inspection models

## 2. Schema Version

Files:

- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/migrations.py`
- `tests/test_storage_bootstrap.py`
- new `tests/test_migrations.py`

Changes:

- advance schema version from `1` to `2`
- extend `WorkItemRow` with:
  - `dataset_id: str | None`
  - `feature_columns: list[str]` stored as JSON
  - `target_columns: list[str]` stored as JSON

Do not modify `DatasetRow` beyond what already exists.

Pseudo-code:

```python
class WorkItemRow(SQLModel, table=True):
    __tablename__ = "work_item"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    name: str = Field(index=True)
    description: str | None = None
    dataset_id: str | None = Field(default=None, foreign_key="dataset.id", index=True)
    feature_columns: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    target_columns: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
```

Migration algorithm:

1. create `work_item_v2` with the new columns
2. copy old rows with:
   - `dataset_id = NULL`
   - `feature_columns = []`
   - `target_columns = []`
3. replace old `work_item`
4. set `PRAGMA user_version=2`

## 3. Repository Changes

Files:

- `src/xenix/services/storage/repositories/work_items.py`
- `src/xenix/services/storage/repositories/__init__.py`

Changes:

- add:
  - `set_dataset_selection(session, work_item_id, dataset_id, feature_columns, target_columns, now) -> WorkItemRow | None`

Pseudo-code:

```python
def set_dataset_selection(...):
    row = self.get(session, work_item_id)
    if row is None:
        return None
    row.dataset_id = dataset_id
    row.feature_columns = list(feature_columns)
    row.target_columns = list(target_columns)
    row.updated_at = now
    session.add(row)
    session.flush()
    session.refresh(row)
    return row
```

## 4. Dataset Inspection Models

Files:

- new `src/xenix/services/dataset_inspection.py`

Add Pydantic models:

- `DatasetColumnKind`
- `DatasetColumnMetadata`
- `DatasetInspection`
- `InspectDatasetInput`
- `PersistDatasetSelectionInput`

Suggested model shapes:

```python
class DatasetColumnKind(StrEnum):
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"
    DATETIME = "datetime"
    TEXT = "text"
    UNKNOWN = "unknown"


class DatasetColumnMetadata(BaseModel):
    name: str
    kind: DatasetColumnKind
    nullable: bool


class DatasetInspection(BaseModel):
    source_path: str
    source_format: DatasetSourceFormat
    file_name: str
    row_count: int
    column_count: int
    columns: list[DatasetColumnMetadata]
```

## 5. Dataset Inspection Service

Files:

- `src/xenix/services/dataset_service.py`
- optionally new `src/xenix/services/dataframe_loader.py`

Changes:

- keep `register_dataset()`, `list_datasets()`, and `get_dataset()`
- add `inspect_source_file(input_data: InspectDatasetInput) -> DatasetInspection`
- remove the temp-copy helper from the public `#75` flow
- mark `materialize_read_copy()` as no longer used by import flow and prepare it for later removal by `#72`

Implementation algorithm for inspection:

1. validate that `source_path` is absolute, exists, and has a supported suffix
2. load dataframe:
   - `.csv` -> `pandas.read_csv`
   - `.xlsx` / `.xls` -> `pandas.read_excel`
3. reject:
   - empty file
   - zero-column dataframe
4. infer column kinds from pandas dtypes
5. return `DatasetInspection`

Pseudo-code:

```python
def inspect_source_file(self, input_data: InspectDatasetInput) -> DatasetInspection:
    source_path = Path(input_data.source_path).expanduser()
    source_format = _detect_source_format(source_path)
    df = _load_dataframe(source_path, source_format)
    if df.empty and len(df.columns) == 0:
        raise ValidationError("Dataset file is empty.")
    columns = [
        DatasetColumnMetadata(
            name=str(column_name),
            kind=_infer_column_kind(df[column_name]),
            nullable=bool(df[column_name].isna().any()),
        )
        for column_name in df.columns
    ]
    return DatasetInspection(
        source_path=str(source_path),
        source_format=source_format,
        file_name=source_path.name,
        row_count=len(df.index),
        column_count=len(df.columns),
        columns=columns,
    )
```

## 6. Persist Dataset Selection On Work Item

Files:

- `src/xenix/services/work_item_service.py`
- possibly new request DTO module if it keeps things cleaner

Add:

- `AttachDatasetSelectionInput`
- `attach_dataset_selection(input_data) -> WorkItemRow`

Validation rules:

- work item must exist
- dataset must exist
- dataset project must equal work-item project
- selected columns must be subsets of the inspected dataset columns
- `feature_columns` must not be empty
- `feature_columns` and `target_columns` must not overlap

Do not require non-empty `target_columns` in `#75`.
That keeps the persisted selection compatible with future unsupervised flows.

Pseudo-code:

```python
def attach_dataset_selection(self, input_data: AttachDatasetSelectionInput) -> WorkItemRow:
    inspection = self._dataset_service.inspect_source_file(
        InspectDatasetInput(source_path=dataset.source_path)
    )
    available = {column.name for column in inspection.columns}
    if not set(input_data.feature_columns).issubset(available):
        raise ValidationError("Selected feature columns are invalid.")
    if not set(input_data.target_columns).issubset(available):
        raise ValidationError("Selected target columns are invalid.")
    if set(input_data.feature_columns) & set(input_data.target_columns):
        raise ValidationError("Feature and target columns cannot overlap.")
    updated = self._work_items.set_dataset_selection(...)
```

## 7. Service Wiring

Files:

- `src/xenix/app.py`
- `src/xenix/ui/main_window.py`

Changes:

- construct:
  - `ProjectService`
  - `WorkItemService`
  - `DatasetService`
- inject them into the main window or a workspace widget

Do not instantiate pandas-aware logic in the UI directly.
