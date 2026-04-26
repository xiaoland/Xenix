# Clustering Profile V1.5 Solidify Task

## Input Classification

- Type: `Intent`
- Requested outcome:
  - track cluster profile output as a slice separate from P1.5 model usability
  - build on the existing `cluster_assignments.csv` openable output
  - keep implementation paused until explicit `start`

## Objective & Hypothesis

- Objective: make clustering results interpretable beyond row-level cluster assignments.
- Hypothesis: clustering becomes business-usable when each cluster has a compact profile artifact and UI summary: row count, numeric means, and top categorical values.

## Address and Object

- Task packet:
  - `tasks/model-support-gap/clustering-profile-v1-5-solidify.md`
- Durable owners expected in this slice:
  - `src/xenix/services/ml/models/base.py`
  - `src/xenix/services/ml/models/clustering.py`
  - `src/xenix/services/ml/contracts.py`
  - `src/xenix/services/ml_task_service.py`
  - `src/xenix/services/scenario_workflow_service.py`
  - `src/xenix/ui/scenario_training_dialog.py`
  - `src/xenix/translations/xenix_en_US.ts`
  - `src/xenix/translations/xenix_zh_CN.ts`
  - `tests/test_ml_execution.py`
  - `tests/test_scenario_workflow.py`
  - `tests/test_scenario_ui.py`

## State Diff

- From:
  - clustering fit writes `cluster_assignments.csv`
  - training dashboard can open the selected clustering output CSV
  - result summary includes cluster count, noise count, row count, and cluster column name
- To:
  - clustering fit additionally writes a profile artifact such as `cluster_profile.csv`
  - result summary includes compact profile facts for display
  - dashboard can expose the profile artifact in a clear way

## Scope

- Generate cluster profile data from the post-fit assignment frame:
  - one row per cluster
  - row count per cluster
  - numeric feature means per cluster
  - top categorical value per cluster for selected categorical features
  - optional noise row summary when the estimator emits noise label `-1`
- Persist a profile artifact:
  - expected file name: `cluster_profile.csv`
  - artifact kind should be openable from training dashboard
  - keep `cluster_assignments.csv` as the row-level output
- Surface concise UI summary:
  - include row count and profile availability in clustering cards or task details
  - preserve the current `Close Results` terminal behavior

## Out of Scope

- Visual charts.
- Cluster naming or automatic business labels.
- Scenario recommendation based on cluster profile.
- Supervised model-selection usability changes; tracked in `p1-5-solidify.md`.
- New clustering algorithms.

## Blast Radius Forecast

- Low blast radius:
  - clustering service output generation
  - result summary shape additions
  - tests around artifacts and summary fields
- Medium blast radius:
  - `MLTaskArtifact` finalization if one fit task now emits multiple openable exports
  - training dashboard output action if it needs to choose among multiple openable files
- Stable surfaces:
  - clustering remains feature-only
  - clustering still has no evaluation or inference gate
  - `cluster_assignments.csv` remains available
  - supervised task lifecycle remains unchanged

## Invariants Check

- Keep clustering fit deterministic for the same estimator parameters and random state.
- Keep row-level assignments export intact.
- Keep profile generation bounded to selected feature columns plus cluster metadata.
- Keep profile output CSV readable by standard spreadsheet tooling.
- Keep task completion robust when a selected categorical feature has missing values.

## Verification

- Static:
  - `pdm run python -m compileall src tests scripts`
- Targeted:
  - `pdm run pytest tests/test_ml_execution.py tests/test_scenario_workflow.py tests/test_scenario_ui.py -q`
- Full:
  - `pdm run pytest -q`
- Behavioral anchors:
  - clustering fit writes `cluster_assignments.csv`
  - clustering fit writes `cluster_profile.csv`
  - result summary exposes profile row count or equivalent profile availability metadata
  - training dashboard can open clustering output artifacts after a successful run
  - existing supervised training and inference tests keep passing

## Confirmation State

- User requested this as a separate slice from P1.5 model usability.
- Implementation remains gated on an explicit `start`.
