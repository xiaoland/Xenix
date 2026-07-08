# Lazy Export And Link Router

## Objective & Hypothesis

Historical committed slice: separate dataset identity from artifact identity by introducing LinkRouter and lazy dataset workbook export. This path is now superseded globally, but the LinkRouter boundary remains useful for artifact and external link activation.

## Status

superseded

## Durable Owners / Blast Radius

- `LinkRouter`
- `DatasetExportService`
- `ArtifactService`
- artifact link docs
- system prompt / tool result guidance
- Chatbot link activation path

## State Diff

From: generated dataset tools could expose both dataset ids and artifact ids, and the model could put a dataset id inside `artifact://`.

To in committed slice `542561f`: dataset-producing tools return `dataset_uri`; `artifact://` stays artifact-only; `dataset://` lazily exports a workbook artifact and opens through `ArtifactService`.

Superseding target after `9d0de57`: keep `LinkRouter`, but remove `dataset://` globally. Derived dataset-producing tools should synchronously create export artifacts before returning and provide `artifact_id` values; the System Prompt explains how to form `artifact://<artifact_id>` links.

## Invariants

- UI does not resolve service-owned paths or open local artifact files itself.
- `artifact://` never falls back to dataset lookup.
- Historical invariant only: `dataset://` may create/reuse an artifact internally but remains dataset-id authority.
- New target invariant: user-facing dataset result links should be artifact links to already-created export artifacts.
- Exported workbook artifacts are user-openable; internal Parquet files are not.

## Decisions Consumed

- Link activation belongs to `LinkRouter`.
- Dataset export activation belongs to `DatasetExportService`.
- File opening belongs to `ArtifactService`.

## Open Questions

- OQ-002: future multi-sheet/group workbook export semantics.
- OQ-007: generated dataset scope for eager export artifacts.

## Historical Verification Plan

- Activating `dataset://<dataset_id>` materializes/reuses an `.xlsx` artifact.
- Repeated activation reuses the artifact.
- Activating `artifact://<artifact_id>` opens through `ArtifactService`.
- Missing dataset/artifact identities fail in their own authority boundary.

## Verification Run Log

- Covered by `pdm run python -m pytest -q`: 304 passed, 3 warnings.
- This verifies the committed lazy path, not the new eager export target.

## Next Action

Do not extend this lazy path. Implement global removal in `../08-eager-derived-export-artifacts/packet.md`.
