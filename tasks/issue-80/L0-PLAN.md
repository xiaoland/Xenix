# Issue 80 - L0 Analysis and Scope Clarification

## Task Intent

Clarify and rewrite issue #80 description so that implementation can later proceed with stable requirements.

Current collaboration rule for this task:

- No code implementation yet.
- Iterate on issue description quality and testable acceptance criteria.

## Source Inputs

- GitHub issue #80 current state: mostly template placeholders, unclear specification.
- New product direction provided by requester:
  - Audience: non-technical users.
  - Rebuild UI/UX/User Journey around scenario templates.
  - Introduce Settings window.
  - Home becomes scenario-card grid plus two utility entries (Settings, History).
  - Guided three-window flow after selecting a scenario card:
    1. Window A: data upload and optional variable-column selection.
    2. Window B: training dashboard with task/log/metrics and one-click full retrain.
    3. Window C: inference input and prediction execution with automatic persistence linked to WorkItem.
  - History list should show inference results (not all WorkItems), with time sort and time-range filter.

## Current State (Observed in Codebase)

1. Main UI is tab-based (Datasets, Training, Inference), not scenario-card based.
2. WorkItem lifecycle already exists:
   - Dataset + column selection + WorkItem creation in dataset workspace.
3. Training capabilities already exist:
   - Fit/Tuning/Evaluate task pipeline.
   - Task queue, task logs, and best-model update after evaluation.
4. Inference capabilities already exist:
   - Manual row input and batch file inference.
   - Inference results persisted and linked through task/result dataset metadata.
5. There is no dedicated history-entry page focused only on inference outcomes.
6. There is no dedicated settings window as a standalone UX surface.

## Gap Between Current and Target

1. IA/Navigator gap:
   - Current: three technical tabs.
   - Target: scenario-first home + guided modal/step windows.
2. Cognitive load gap:
   - Current flow exposes project/work item/model operations explicitly.
   - Target flow should hide most technical decisions behind scenario presets.
3. Data-to-result continuity gap:
   - Current flow is workspace switching.
   - Target flow is linear A -> B -> C completion path.
4. Discoverability gap:
   - Current users must understand training/inference separation.
   - Target users pick a business scenario card and follow guided steps.
5. History semantic gap:
   - Current retrieval is task-centric in inference workspace.
   - Target explicitly defines history as inference-result list with date filtering/sorting.

## Confirmed Constraints and Invariants

1. WorkItem remains a key persistence boundary for:
   - dataset linkage
   - feature/target column selections
   - best trained model pointer
2. ML tasks are persisted with statuses/logs and run sequentially in v1.
3. Inference result artifacts already support durable output files and dataset linkage.
4. Native app remains single local operator (no multi-user/session concerns).
5. This issue is currently product-definition work only (no implementation yet).

## Scope Candidate for Issue Description Rewrite

1. Rewrite all major sections in issue #80:
   - Summary
   - Rationale
   - Specification
   - Acceptance Criteria
   - Technical Constraints
   - Backward Compatibility
   - Alternatives Considered
2. Convert request text into testable behavior statements.
3. Explicitly define what is in v1 scope vs deferred.
4. Define success metrics for "non-technical user can finish task quickly".

## Open Questions Requiring Confirmation

1. Scenario templates (home grid)

- What is the v1 fixed card list?
- Is each card mapped to one problem kind (regression/classification/clustering/etc.)?
- Should cards be configurable later, or hardcoded in v1?

1. Window A (data + columns)

- Is project selection still visible to user, or fully hidden/auto-generated?
- For scenarios where variable selection is optional, what is fallback behavior?
- Should users be allowed to modify selected columns later in Window B/C?

1. Window B (training dashboard)

- "Auto training plan" exact composition:
  - which models
  - whether tuning included by default
  - stopping condition
- "Train again fully" semantics:
  - rerun same preset plan only
  - or allow plan editing before rerun?
- Which evaluation metric is primary per scenario?

1. Window C (inference)

- Should C always use current WorkItem best model, or allow model override?
- For manual input mode, is single-row enough or multi-row table required?
- Should prediction outputs support only preview + save, or also export format options in v1?

1. Home and history

- Home has only three entry groups: scenario grid, settings button, history button. Confirm no additional global controls.
- History data unit:
  - one row per inference task result?
  - if one task has multiple output files, show one row or many?
- Time filter granularity:
  - day/week/month/custom range?

1. Settings window

- Which settings are in v1 mandatory set?
  - language
  - data/artifact paths
  - logging behavior
  - model/training defaults
- Should settings changes require app restart?

## Risk Notes for Later Stages

1. Hidden technical complexity may reduce transparency for advanced users.
2. Auto-plan defaults may produce wrong expectations if scenario-card semantics are vague.
3. Rewriting journey without explicit state model may cause dead-end transitions between A/B/C.
4. History definition must align with persisted inference-task/result model to avoid data ambiguity.

## Proposed Next Step (Awaiting Confirmation)

After confirmation on this L0 framing, move to L1:

- Define high-level UX architecture and system behavior boundaries for home, A/B/C windows, settings, and history.
- Provide a first complete draft for issue #80 description in issue-template format.
