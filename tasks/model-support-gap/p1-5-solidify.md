# P1.5 Model Usability Solidify Task

## Input Classification

- Type: `Intent`
- Requested outcome:
  - continue after the verified `P1 supervised model pack`
  - improve model selection and training-result usability before dependency-heavy `P2`
  - split clustering profile output into a dedicated follow-up slice
  - keep implementation paused until explicit `start`

## Objective & Hypothesis

- Objective: make the expanded native model catalog easier for a non-technical business user to choose, run, and compare inside existing scenario workflows.
- Hypothesis: the next highest-leverage slice should improve catalog metadata, scenario default plans, training-selection presentation, and supervised result comparison while staying inside current service/UI boundaries.

## Address and Object

- Task packet:
  - `tasks/model-support-gap/p1-5-solidify.md`
- Durable owners expected in this slice:
  - `src/xenix/services/ml/types.py`
  - `src/xenix/services/ml/models/base.py`
  - `src/xenix/services/ml/models/regression.py`
  - `src/xenix/services/ml/models/classification.py`
  - `src/xenix/services/ml/models/clustering.py`
  - `src/xenix/services/scenario_template_service.py`
  - `src/xenix/services/scenario_training_preset_service.py`
  - `src/xenix/ui/scenario_training_selection_dialog.py`
  - `src/xenix/ui/scenario_training_dialog.py`
  - `src/xenix/translations/xenix_en_US.ts`
  - `src/xenix/translations/xenix_zh_CN.ts`
  - `tests/test_ml_registry.py`
  - `tests/test_scenario_ui.py`
  - `tests/test_scenario_workflow.py`
  - `tests/test_i18n.py`

## State Diff

- From:
  - native catalog has broad P0/P1 model coverage
  - scenario model selection lists compatible models ordered by template default priority and display name
  - model cards show model name, training mode, parameter form, and generic operation guidance
  - scenario defaults still reflect the pre-P0/P1 small catalog
  - training results show per-card metrics and a best-model label, with comparison left mostly implicit
- To:
  - catalog entries include concise user-facing guidance metadata
  - selection cards expose model family, recommendation tier, and short model-fit guidance
  - compatible models are grouped and ordered for business usability
  - supervised scenario defaults include a small curated set from the expanded catalog
  - training dashboard makes result ranking easier to scan for supervised scenarios

## Scope

- Add catalog usability metadata:
  - short guidance text
  - model family
  - recommendation tier or scenario rank
  - optional strengths/caveats where the UI can display them compactly
- Improve training-selection dialog:
  - group or visually separate recommended defaults from additional compatible models
  - sort compatible entries by recommendation tier, scenario default priority, family, then display name
  - show one concise guidance sentence per model card
  - preserve current parameter-form and operation-selection behavior
- Refresh default supervised training plans:
  - regression: keep a small default set that covers linear baseline, regularized linear, and nonlinear tree/boosted behavior
  - classification: keep a small default set that covers linear baseline, probabilistic/simple baseline, and nonlinear tree/boosted behavior
  - avoid excessive default task count so scenario training remains responsive
- Improve supervised result comparison:
  - add visible rank cues or sorted result cards once metrics are available
  - keep best-model persistence and continue-to-prediction behavior unchanged
  - keep clustering dashboard output-file behavior unchanged in this slice

## Out of Scope

- Cluster profile artifacts and summaries; tracked in `tasks/model-support-gap/clustering-profile-v1-5-solidify.md`.
- New dependency families:
  - `xgboost`
  - `lightgbm`
- New problem kinds:
  - association analysis
  - recommendation
  - anomaly scoring
- Storage schema changes.
- Changes to legacy scripts under `F:\CODING\Project\Xenix\ml`.

## Blast Radius Forecast

- Low blast radius:
  - catalog schema expansion if fields have safe defaults
  - model service class metadata
  - selection-card text and order tests
- Medium blast radius:
  - default scenario plan changes because existing tests assert selected model keys
  - translation snapshots and i18n checks for new UI strings
  - result-card ordering if tests assume insertion order
- Stable surfaces:
  - `ProblemKind`
  - `MLTaskType`
  - model training/evaluate/inference contracts
  - work-item persistence
  - clustering fit/export lifecycle

## Invariants Check

- Keep existing trained-model persistence and best-model selection semantics.
- Keep scenario training defaults small enough for local desktop use.
- Keep all P0/P1 model keys available in manual selection.
- Keep model parameter schemas JSON Schema form-renderable.
- Keep catalog metadata optional or defaulted so existing callers can validate entries.
- Keep translations compiled after UI string changes.

## Verification

- Static:
  - `pdm run python -m compileall src tests scripts`
- Targeted:
  - `pdm run pytest tests/test_ml_registry.py tests/test_scenario_ui.py tests/test_scenario_workflow.py tests/test_i18n.py -q`
- Full:
  - `pdm run pytest -q`
- Behavioral anchors:
  - catalog entries validate with the new usability metadata
  - training-selection dialog still opens for regression, classification, and clustering templates
  - default selected supervised model lists match the curated P1.5 plan
  - user-saved default selections still override template defaults
  - supervised result cards surface ranking or equivalent comparison cues
  - clustering output open action from P0 remains available

## Confirmation State

- User agreed with starting a P1.5 usability slice.
- User requested clustering profile output to be tracked as a separate slice.
- User later authorized implementation with `开始 P1.5`.
- Execution is recorded in `tasks/model-support-gap/p1-5-execution.md`.
