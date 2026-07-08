# Eager Derived Export Artifacts

## Objective & Hypothesis

Replace lazy dataset activation with eager export artifacts for generated datasets and remove `dataset://` globally. When an Agent tool creates a derived dataset, the tool should materialize the corresponding user-openable workbook export artifact before returning. The model should receive `dataset_id` for future tool calls and `artifact_id` for user-facing links.

## Status

implemented; focused verification passed

## Durable Owners / Blast Radius

- `AgentToolRegistry._register_generated_dataset_result()` and every Agent-visible generated dataset path.
- `DatasetExportService` or `DatasetService` export materialization API.
- `ArtifactService` artifact registration and `LinkRouter` activation.
- Agent System Prompt and skills that describe dataset/artifact identity.
- UI tests that currently cover `dataset://` activation and service-link progress.
- Product/unit TDD docs for artifact links and dataset storage.

## State Diff

From: generated dataset tools return `dataset_uri`, and user click on `dataset://<dataset_id>` triggers lazy workbook export.

To: generated dataset tools create a workbook export artifact before returning and return `dataset_id` plus `artifact_id`. `dataset://` is removed globally; tools do not return `artifact_uri`.

## Invariants

- Registered dataset identity remains available as `dataset_id` for later tools.
- Internal app-owned Parquet remains the execution source of truth.
- Export artifacts are user-openable materializations, not the dataset execution source.
- Tool completion should be atomic: if the export artifact cannot be created, the tool should not report a successful user-openable derived dataset result.
- `LinkRouter` remains the UI activation boundary for `artifact://` and ordinary external links.
- `ArtifactService` remains the only owner of OS file opening.
- `artifact://` still never falls back to dataset lookup.
- The System Prompt owns the artifact URI format: `artifact://<artifact_id>`.
- The System Prompt should describe artifacts as user-openable/previewable business outputs.

## Decisions Consumed

- Superseding decision in `ledger/decisions.md`: remove `dataset://` globally; eager export artifact for derived datasets.
- App-owned Parquet remains the internal dataset format.
- Dataset export should use Polars, not Pandas.

## Questions Resolved In This Slice

- OQ-007: current implementation covers Agent-visible generated registered datasets that use `AgentToolRegistry._register_generated_dataset_result()`: `data.integrate`, `data.clean`, `data.tokenize`, and `data.transform`.
- OQ-008: default dataset export artifact format is workbook `.xlsx`.

## Verification Plan

- Generated dataset tool payloads include `dataset_id` and `artifact_id`, and exclude `dataset_uri` and `artifact_uri`.
- Tool output waits until the artifact file exists and is registered.
- `artifact://` click still activates through `LinkRouter -> ArtifactService`.
- No production code, docs, skills, prompts, or UI tests rely on `dataset://`.
- System Prompt explains `artifact://<artifact_id>` format and the meaning of artifacts.
- Failed export registration/materialization does not leave a successful-looking tool result.
- Existing internal Parquet query/transform/ML paths remain unchanged.

## Verification Run Log

- `git diff --check`: passed.
- `pdm run pytest tests/test_services.py::test_dataset_export_service_materializes_workbook_artifact tests/test_services.py::test_link_router_rejects_dataset_scheme tests/test_services.py::test_dataset_service_discards_unreferenced_dataset tests/test_data_transform.py::test_data_integrate_tool_uses_dataset_ids_and_returns_artifact_id tests/test_data_transform.py::test_data_transform_tool_discards_dataset_when_export_artifact_fails tests/test_data_transform.py::test_data_transform_tool_registers_derived_dataset_and_returns_artifact_id tests/test_data_transform.py::test_data_transform_tool_records_multi_input_lineage_in_result tests/test_data_cleaning.py::test_data_clean_tool_registers_derived_dataset_and_artifact tests/test_data_tokenization.py::test_data_tokenize_tool_registers_derived_dataset_and_artifact tests/test_main.py::test_main_window_opens_service_link_off_ui_thread tests/test_main.py::test_main_window_service_link_activation_failure_closes_progress`: 11 passed in 10.23s.
- `pdm run python -m compileall -q src/xenix`: passed.
- `pdm run pytest tests/test_services.py tests/test_data_transform.py tests/test_data_cleaning.py tests/test_data_tokenization.py tests/test_main.py -q`: 100 passed in 39.98s.

## Next Action

Run broader regression if time allows, then prepare a focused commit only after explicit commit instruction.
