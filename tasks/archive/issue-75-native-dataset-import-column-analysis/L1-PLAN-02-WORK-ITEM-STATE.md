# L1 Plan 02: Work-Item State

## Ownership Rule

The approved ownership rule is:

- `Dataset` stores imported dataset registration metadata
- `WorkItem` stores the chosen dataset and selected feature/target columns

Why this is the right boundary:

- a dataset can be reused across multiple work items
- different work items may choose different feature/target columns
- later training and inference naturally attach to the work item, not to the dataset record alone

## Work-Item State To Persist

Issue `#75` should persist at least:

- which dataset is currently attached to the work item
- which feature columns are selected for that work item
- which target columns are selected for that work item

This makes `WorkItem` the local aggregator for:

- dataset
- training
- inference

which matches the issue background and later issue `#72` / `#73` expectations.

## Dataset Inspection Metadata Rule

Do not persist dataset inspection output by default.

Do not add to `Dataset`:

- row count
- inferred column kinds
- preview samples
- feature/target selections

Reasoning:

- the source file can change outside the app
- persisted inspection data would go stale quickly
- the database would start carrying derived state that is not the canonical truth

## High-Level Storage Direction

Issue `#75` likely requires a storage extension on `WorkItem`.

High-level direction for later stages:

- add dataset linkage to `WorkItem`
- add feature-column selection to `WorkItem`
- add target-column selection to `WorkItem`

The exact schema change belongs in L2.

## Impact On Issue `#72`

This decision simplifies issue `#72`:

- training will start from the work item's selected dataset and columns
- issue `#72` will not need to invent a second persistence location for dataset setup
- the best-model field later added by issue `#72` will live on the same entity that already aggregates dataset + training + inference state

This is the cleanest ownership split across the native roadmap.

## Hidden UI Consequence

Because work-item state is now part of issue `#75`, the import flow must include one of:

- work-item selection
- work-item creation
- both

Issue `#75` therefore cannot remain only a file import dialog. It needs a minimal project/work-item context surface.
