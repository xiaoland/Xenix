# Issue 80 - L2 UX Adaptation Plans (Reuse + Transformation)

## Purpose

Define concrete adaptation work on top of reused UI components so the scenario workflow is genuinely non-technical-user friendly.

This document complements L2-PLAN and focuses only on UX adaptation depth.

## Design Principle

Reuse is the technical strategy, but adaptation is the product strategy.

For non-technical users, each screen should:

1. Explain what to do in business language.
2. Hide technical choices by default.
3. Offer one primary next action.
4. Keep advanced details behind progressive disclosure.

## Scope Guardrails

1. This plan must not add new business capability requirements.
2. Disallowed in issue 80 scope:

- automatic column recommendation/suggestion logic
- new business summary functions (for example, compute_training_run_summary)
- any change to model evaluation or best-model selection policy

3. Reuse is a means, not a goal:

- avoid over-reuse when a reused component keeps technical complexity exposed.
- allow targeted replacement of view components while keeping existing service contracts.

4. This UX plan must align with the current architecture:

- scenario mode hides project completely
- v1 training progress is backed by the current sequential ML task runner
- history must remain valid without persisted scenario labels

## Plan A - Guided Baseline (v1 Must-Have)

Goal:

- Reach minimum non-technical usability without large architecture risk.

## A1. Window A (Data Preparation) Adaptations

1. Component: FileDropZone

- Current gap:
  - Generic wording and low guidance.
- Adaptation:
  - replace copy with scenario-specific text and examples.
  - add explicit secondary action text: click to choose file.
  - add inline validation feedback (file accepted / unsupported format).

1. Component: DatasetSummaryWidget

- Current gap:
  - technical metadata-centered layout.
- Adaptation:
  - default to friendly summary cards:
    - record count
    - field count
    - upload/inspection readiness
  - move file path/format into expandable advanced details.

1. Component: ColumnSelectionWidget

- Current gap:
  - dual-list feature/target selection is technical and error-prone.
- Adaptation:
  - convert to guided two-step interaction:
    1. choose prediction target
    2. choose input columns explicitly
  - prevent overlap through immediate UI validation using existing rules.
  - rename labels in business language (Input Columns / Prediction Target).

1. Component source: DatasetWorkspace logic

- Current gap:
  - project/work-item controls expose system internals.
- Adaptation:
  - hide project selector in scenario mode.
  - resolve the hidden scenario project automatically.
  - hide manual naming by default and keep dataset-based prefill as the fallback behavior.
  - keep existing naming behavior (dataset-based prefill) without adding new naming algorithms.
  - primary CTA text becomes Continue to Training.

## A2. Window B (Training Dashboard) Adaptations

1. Component source: MLWorkspace runtime panel

- Current gap:
  - model/tuning controls and technical tabs increase cognitive load.
- Adaptation:
  - hide manual fit/tuning editors in scenario mode.
  - keep only:
    - fixed-plan progress summary
    - task status list
    - best model result card
    - Run Full Plan Again
    - Continue to Prediction
  - do not imply parallel execution in the default UI copy; progress should reflect the ordered plan backed by the existing task queue.

1. Component: TaskLogView

- Current gap:
  - raw logs are too technical.
- Adaptation:
  - add plain-language status summary above logs:
    - what is running now
    - what completed
    - whether user needs action
  - derive text from existing task status fields only (no new summary service/function).
  - raw logs available in collapsible Advanced panel.

## A3. Window C (Inference) Adaptations

1. Component: InferenceRowEditorWidget

- Current gap:
  - raw table-first editing is intimidating.
- Adaptation:
  - default to form mode for single prediction.
  - keep table mode behind "Batch / Advanced" toggle.
  - show required-field validation in plain language.

1. Component source: InferenceWorkspace

- Current gap:
  - project/work item/model selectors are technical.
- Adaptation:
  - auto-bind to scenario session context.
  - default to best model and hide model selector in scenario mode.
  - one primary CTA: Start Prediction.

## A4. Settings/Home Adaptations

1. Component source: MainWindow language/path controls

- Current gap:
  - controls mixed into main work surface.
- Adaptation:
  - move to dedicated Settings dialog.
  - keep Home minimal: scenario cards + Settings + History.

## Plan B - Confidence Layer (v1 Should-Have)

Goal:

- Reduce user anxiety and improve trust during long-running training.

1. Component source: MLWorkspace + TaskLogView

- Adaptation:
  - provide user-facing terminology mapping for existing statuses (Pending/Running/Succeeded/Failed).
  - show non-blocking partial-failure guidance:
    - "Some models failed, but usable result is available."

1. Component source: InferenceWorkspace result panel

- Adaptation:
  - add result explanation card:
    - which model was used
    - how many rows were predicted
    - where output is saved
  - provide quick actions:
    - open file
    - export copy

## Plan C - Progressive Disclosure & Advanced Path (Post-v1)

Goal:

- Keep non-technical default simple while supporting power users.

1. Component: JsonSchemaFormWidget

- Adaptation:
  - hidden by default in scenario flow.
  - surfaced only in "Advanced Training Options" drawer.
  - provide presets first, free-form schema fields second.

1. Component source: all A/B/C dialogs

- Adaptation:
  - add Expert Mode toggle at dialog level.
  - when enabled, reveal model and task technical panels without making project a primary concept again.

## Component Adaptation Matrix

1. FileDropZone

- Reuse: yes
- Adapt: copy, guidance, validation state

1. DatasetSummaryWidget

- Reuse: yes
- Adapt: friendly summary default + advanced collapse

1. ColumnSelectionWidget

- Reuse: conditional
- Adapt: guided step flow + explicit user selection + overlap prevention

1. DatasetWorkspace behavior

- Reuse: yes
- Adapt: hide project/work item internals in scenario mode

1. MLWorkspace runtime panel

- Reuse: partial
- Adapt: remove manual technical controls in scenario mode

1. TaskLogView

- Reuse: yes
- Adapt: plain-language status layer + advanced raw logs

1. InferenceRowEditorWidget

- Reuse: conditional
- Adapt: form-first mode + advanced table mode

1. InferenceWorkspace behavior

- Reuse: yes
- Adapt: auto context binding + single primary CTA

1. MainWindow controls

- Reuse: yes
- Adapt: move to dedicated Settings dialog

1. JsonSchemaFormWidget

- Reuse: partial
- Adapt: advanced-only exposure and presets-first UX

## Delivery Order Recommendation

1. Execute Plan A fully before any new feature surface.
2. Execute Plan B if schedule allows in the same issue scope.
3. Keep Plan C as post-v1 unless user testing shows immediate need.

## Anti-Over-Reuse Decision Rules

1. If a reused panel still exposes more than two technical decisions on the default path, replace the panel.
2. If required adaptation creates high coupling to legacy workspace state, replace the panel.
3. If replacement is chosen, preserve existing service contracts and persistence ownership.

## UX Acceptance Signals

1. First-time users can complete A -> B -> C without understanding terms like WorkItem, tuning grid, or model key.
2. Each screen has a single obvious next action.
3. Advanced controls exist but do not block the default path.
4. User can recover from invalid input with plain-language feedback.
