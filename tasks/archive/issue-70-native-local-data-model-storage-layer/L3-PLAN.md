# L3 Plan

## Stage Goal

Translate the approved L2 design into a concrete implementation roadmap for issue `#70`, including file-by-file changes, execution order, pseudo-code, and the verification plan.

## Implementation Outcome

After this plan is implemented, the native branch should have:

- expanded runtime directories for state, temp, and artifacts
- a SQLModel-backed SQLite bootstrap path
- schema version `1` initialized and tracked with `PRAGMA user_version`
- foundational persistence for `project`, `work_item`, `dataset`, `ml_task`, and `ml_task_artifact`
- service-owned metadata CRUD and ML task state transitions
- service-owned dataset temp-copy materialization and cleanup
- documentation updates describing the runtime state and storage ownership changes

## Execution Order

Implement in this order:

1. Dependency and runtime-path foundation
2. Storage layout helpers and database bootstrap
3. SQLModel schema and repositories
4. Service DTOs and service implementations
5. Application bootstrap wiring
6. Automated tests
7. Documentation updates

This order keeps failures local and prevents building services on unstable storage primitives.

## File-by-File Plan

### 1. Dependency and runtime-path foundation

Files:

- `pyproject.toml`
- `src/xenix/config.py`
- `tests/test_config.py`

Changes:

- add `sqlmodel` to runtime dependencies
- extend `AppPaths` with:
  - `state`
  - `temp`
  - `artifacts`
- ensure `ensure_app_dirs()` creates the new top-level directories
- extend config tests to assert the new directories are created

Pseudo-code:

```python
@dataclass(frozen=True)
class AppPaths:
    home: Path
    config: Path
    logs: Path
    cache: Path
    state: Path
    temp: Path
    artifacts: Path
    resources: Path


def get_app_paths() -> AppPaths:
    home = _default_app_home()
    return AppPaths(
        home=home,
        config=home / "config",
        logs=home / "logs",
        cache=home / "cache",
        state=home / "state",
        temp=home / "temp",
        artifacts=home / "artifacts",
        resources=package_root / "resources",
    )
```

### 2. Storage layout helpers and database bootstrap

Files:

- `src/xenix/services/__init__.py`
- `src/xenix/services/storage/__init__.py`
- `src/xenix/services/storage/layout.py`
- `src/xenix/services/storage/database.py`
- `src/xenix/services/storage/migrations.py`
- new tests file: `tests/test_storage_bootstrap.py`

Changes:

- create storage package
- implement runtime layout helper functions
- implement engine creation
- implement session factory creation
- implement migration runner with `CURRENT_SCHEMA_VERSION = 1`
- implement `PRAGMA user_version` read/write helpers
- add tests for schema bootstrap and version tracking

Pseudo-code:

```python
def database_path(paths: AppPaths) -> Path:
    return paths.state / "xenix.db"


def ml_task_root(paths: AppPaths, ml_task_id: str) -> Path:
    return paths.artifacts / "ml-tasks" / ml_task_id


def create_engine_for_path(db_path: Path) -> Engine:
    db_url = f"sqlite:///{db_path}"
    return create_engine(db_url, echo=False)


def get_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(connection.exec_driver_sql("PRAGMA user_version").scalar_one())


def apply_v1(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    set_user_version(engine, 1)
```

Implementation note:

- `PRAGMA user_version` is the only acceptable raw SQL in this task

### 3. SQLModel schema and repositories

Files:

- `src/xenix/services/storage/models.py`
- `src/xenix/services/storage/repositories/__init__.py`
- `src/xenix/services/storage/repositories/projects.py`
- `src/xenix/services/storage/repositories/work_items.py`
- `src/xenix/services/storage/repositories/datasets.py`
- `src/xenix/services/storage/repositories/ml_tasks.py`
- new tests file: `tests/test_repositories.py`

Changes:

- define shared enums
- define five table models
- define JSON fields for ML task payloads
- implement explicit repository operations
- add repository CRUD tests

Pseudo-code:

```python
class ProjectRow(SQLModel, table=True):
    __tablename__ = "project"
    id: str = Field(primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class MLTaskRow(SQLModel, table=True):
    __tablename__ = "ml_task"
    id: str = Field(primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    work_item_id: str = Field(foreign_key="work_item.id", index=True)
    dataset_id: str | None = Field(default=None, foreign_key="dataset.id", index=True)
    task_type: MLTaskType = Field(index=True)
    status: MLTaskStatus = Field(index=True)
    request_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    result_payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
```

Repository implementation posture:

- explicit `select(...)` queries
- `session.add(...)`, `session.commit()`, `session.refresh(...)` where appropriate
- no relationship traversal

### 4. Service DTOs and service implementations

Files:

- `src/xenix/services/project_service.py`
- `src/xenix/services/work_item_service.py`
- `src/xenix/services/dataset_service.py`
- `src/xenix/services/ml_task_service.py`
- `src/xenix/services/ml/__init__.py`
- `src/xenix/services/ml/types.py`
- `src/xenix/services/ml/registry.py`
- optionally update `src/xenix/exceptions.py`
- new tests file: `tests/test_services.py`

Changes:

- create input DTOs and helper result models
- implement each top-level service around a shared session factory
- implement dataset source validation and source-format detection
- implement `MaterializedDatasetCopy` context-like helper
- implement ML task transition validation
- stub a minimal native ML registry surface without introducing real training logic

Pseudo-code for dataset temp copy:

```python
class MaterializedDatasetCopy:
    def __init__(self, dataset_id: str, owner_id: str, source_path: Path, copied_path: Path):
        ...

    def cleanup(self) -> None:
        if self.copied_path.exists():
            self.copied_path.unlink()
        owner_dir = self.copied_path.parent
        if owner_dir.exists() and not any(owner_dir.iterdir()):
            owner_dir.rmdir()

    def __enter__(self) -> "MaterializedDatasetCopy":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()
```

Pseudo-code for ML task state transitions:

```python
ALLOWED_TRANSITIONS = {
    MLTaskStatus.PENDING: {MLTaskStatus.RUNNING, MLTaskStatus.CANCELLED},
    MLTaskStatus.RUNNING: {
        MLTaskStatus.SUCCEEDED,
        MLTaskStatus.FAILED,
        MLTaskStatus.CANCELLED,
    },
}


def _require_transition(current: MLTaskStatus, target: MLTaskStatus) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(...)
```

Pseudo-code for completion artifact validation:

```python
def complete_ml_task(input: CompleteMLTaskInput) -> MLTaskRow:
    task = repo.get(...)
    _require_transition(task.status, MLTaskStatus.SUCCEEDED)
    for artifact in input.artifacts:
        if not Path(artifact.absolute_path).exists():
            raise ValidationError(...)
    return repo.complete(...)
```

ML registry implementation posture:

- define `ModelDefinition` data model
- provide `list_model_definitions()` returning an empty list or a minimal placeholder registry in `#70`
- avoid wrapping legacy `ml/` scripts into executable business logic in this issue

### 5. Application bootstrap wiring

Files:

- `src/xenix/app.py`
- optionally `src/xenix/ui/main_window.py`

Changes:

- initialize storage bootstrap during app startup
- ensure the database file and schema exist before showing UI
- optionally show the resolved database path in the shell UI if that adds debugging value without clutter

Pseudo-code:

```python
def run() -> int:
    paths = ensure_app_dirs(get_app_paths())
    log_path = setup_logging(paths)
    storage_context = StorageBootstrapService().initialize(paths)
    app = create_application()
    window = MainWindow(paths=paths, log_path=log_path)
```

If the UI is updated, keep it minimal:

- add `State` path and `Database` path display
- do not surface repository/service details in the shell

### 6. Automated tests

Files:

- `tests/test_config.py`
- `tests/test_storage_bootstrap.py`
- `tests/test_repositories.py`
- `tests/test_services.py`

Test matrix:

- `test_app_paths_include_state_temp_artifacts`
- `test_storage_bootstrap_creates_database_and_sets_user_version`
- `test_migration_runner_is_idempotent_for_version_1`
- `test_project_repository_round_trip`
- `test_work_item_repository_round_trip`
- `test_dataset_repository_round_trip`
- `test_ml_task_repository_round_trip`
- `test_ml_task_completion_persists_artifacts`
- `test_dataset_service_materializes_and_cleans_temp_copy`
- `test_ml_task_service_rejects_invalid_state_transition`

Testing posture:

- use `tmp_path`
- use `XENIX_APP_HOME` override
- use real SQLite files, not mocks
- prefer service-level tests for behavior and repository-level tests for data correctness

### 7. Documentation updates

Files:

- `docs/20-product-tdd/storage-ownership.md`
- `docs/20-product-tdd/task-lifecycle.md`
- `docs/40-deployment/runtime-state.md`
- optionally `README.md`

Changes:

- document `state/`, `temp/`, `artifacts/`
- document `state/xenix.db`
- document that datasets remain external and temp copies are execution-scoped
- document that ML tasks get standalone working directories under `artifacts/ml-tasks/<ml-task-id>/`
- document that per-task process logs may live there, while canonical app logs remain under `logs/`

## Detailed Sequencing

### Phase 1

- update `pyproject.toml`
- update `config.py`
- update `test_config.py`
- run `pdm run test`

Success criteria:

- no existing tests regress
- new top-level directories are created

### Phase 2

- add storage bootstrap modules
- add migration/version tests
- run `pdm run test`

Success criteria:

- database file is created under `state/`
- `PRAGMA user_version` is `1`
- rerunning bootstrap is idempotent

### Phase 3

- add table models and repositories
- add CRUD tests
- run `pdm run test`

Success criteria:

- all foundational entities persist correctly
- JSON payload fields round-trip correctly

### Phase 4

- add services, DTOs, and exceptions
- add dataset temp-copy and ML task transition tests
- run `pdm run test`

Success criteria:

- service validation works
- temp copies are cleaned up
- invalid ML task transitions fail cleanly

### Phase 5

- wire bootstrap into app startup
- update docs
- run `pdm run check`
- run `pdm run test`

Success criteria:

- app startup still succeeds
- docs match implemented behavior

## Implementation Boundaries

Do not implement in `#70`:

- actual subprocess execution of ML tasks
- training orchestration
- inference orchestration
- model artifact ranking or best-model designation
- schema caching or profiling persistence

Only prepare for them:

- ML task working-directory layout
- artifact persistence structure
- generic request/result payload storage

## Risks and Mitigations

### Risk: SQLModel JSON-column typing friction

Mitigation:

- keep payload columns generic
- use SQLAlchemy `Column(JSON, ...)` explicitly
- cover round-trip behavior with repository tests

### Risk: accidental over-modeling of training/inference semantics

Mitigation:

- keep `services/ml/registry.py` minimal
- store generic ML task payloads without hardcoding future workflow details

### Risk: cleanup failures for temp dataset copies

Mitigation:

- make cleanup best-effort and idempotent
- test both normal cleanup and repeated cleanup calls

### Risk: logging contract drift

Mitigation:

- preserve canonical app log behavior under `paths.logs`
- document per-ML-task logs as supplementary, not canonical

## Verification Commands

Planned verification commands after implementation:

```bash
pdm run test
pdm run check
```

Optional manual verification:

```bash
pdm run dev
```

Then confirm:

- the app still starts
- `XENIX_APP_HOME/state/xenix.db` exists
- `XENIX_APP_HOME/temp/` and `XENIX_APP_HOME/artifacts/` exist

## Approval Gate to Execute

Implementation should proceed exactly against this L3 unless a concrete code-discovery issue forces a narrow adjustment.

Execution scope:

- code changes under `src/xenix/`
- tests under `tests/`
- docs updates under `docs/`
- no training or inference workflow implementation

