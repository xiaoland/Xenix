# Change Map

## Durable Owners Touched

- Agent tool registry and tool payload contracts:
  - `src/xenix/services/agent/tools.py`
  - `src/xenix/services/agent/tool_presentations.py`
  - Agent skills and dev fixtures
- Agent Harness result replay:
  - `src/xenix/services/agent/harness_service.py`
  - conversation/tool-call storage surfaces
- Dataset service and storage:
  - `src/xenix/services/dataset_service.py`
  - `src/xenix/services/dataset_inspection.py`
  - `src/xenix/services/storage/models.py`
  - `src/xenix/services/storage/migrations.py`
- Data execution:
  - `src/xenix/services/data_transform.py`
  - `src/xenix/services/tabular.py`
  - cleaning/tokenization/analysis services that load registered datasets
- ML:
  - `src/xenix/services/ml/dataset_loader.py`
  - `src/xenix/services/ml_service.py`
  - `src/xenix/services/ml_task_service.py`
- Link activation and artifacts:
  - `src/xenix/services/link_router.py`
  - `src/xenix/services/dataset_export_service.py`
  - `src/xenix/services/artifact_service.py`
- UI:
  - `src/xenix/ui/chatbot.py`
  - `src/xenix/ui/main_window.py`
  - translation catalogs
- Durable docs:
  - `docs/10-prd/`
  - `docs/20-product-tdd/`
  - `docs/30-unit-tdd/`
  - `docs/40-deployment/`

## Blast Radius

- Existing runtime DB rows may have legacy dataset semantics. This is tracked by OQ-001.
- Packaging now depends on `xlsxwriter` for Polars XLSX export. This is tracked by OQ-005.
- Remote ML worker staging may need explicit Parquet-path verification. This is tracked by OQ-006.
- Future Agent behavior depends on skills and prompt guidance avoiding stale `data.peek` recipes.

## Invariants

- Tools must not expose raw local filesystem paths as user-facing links.
- LLM-authored SQL must use aliases, not service-owned file paths.
- Internal app-owned Parquet files are not user-openable artifacts by default.
- Dataset activation may create/reuse an artifact; artifact activation must not perform dataset lookup fallback.
- Failed transforms must not create half-success durable datasets.
