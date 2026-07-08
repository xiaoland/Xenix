# Lazy Export And Link Router

## Objective & Hypothesis

Separate dataset identity from artifact identity. Dataset links should activate lazy workbook export, while artifact links should activate existing artifact files.

## Status

verified

## Durable Owners / Blast Radius

- `LinkRouter`
- `DatasetExportService`
- `ArtifactService`
- artifact link docs
- system prompt / tool result guidance
- Chatbot link activation path

## State Diff

From: generated dataset tools could expose both dataset ids and artifact ids, and the model could put a dataset id inside `artifact://`.

To: dataset-producing tools return `dataset_uri`; `artifact://` stays artifact-only; `dataset://` lazily exports a workbook artifact and opens through `ArtifactService`.

## Invariants

- UI does not resolve service-owned paths or open local artifact files itself.
- `artifact://` never falls back to dataset lookup.
- `dataset://` may create/reuse an artifact internally but remains dataset-id authority.
- Exported workbook artifacts are user-openable; internal Parquet files are not.

## Decisions Consumed

- Link activation belongs to `LinkRouter`.
- Dataset export activation belongs to `DatasetExportService`.
- File opening belongs to `ArtifactService`.

## Open Questions

- OQ-002: future multi-sheet/group workbook export semantics.

## Verification Plan

- Activating `dataset://<dataset_id>` materializes/reuses an `.xlsx` artifact.
- Repeated activation reuses the artifact.
- Activating `artifact://<artifact_id>` opens through `ArtifactService`.
- Missing dataset/artifact identities fail in their own authority boundary.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.

## Next Action

Observe whether users need "export workbook group" behavior after single-dataset activation stabilizes.
