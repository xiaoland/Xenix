# UI Layer Guidance

## Scope

This guidance applies to `src/xenix/ui/` except `src/xenix/ui/widgets/`, which may add narrower local rules.

## Rules

- Keep scenario mode as the default operator path. `MainWindow`, Home, Window A/B/C, History, and Settings are first-class UI surfaces.
- Do not reintroduce project or work-item selectors into scenario dialogs. Scenario mode may hide those details, but the UI must still obtain ids and paths from services.
- UI code must stay service-driven. Do not parse datasets, invent storage paths, or reconstruct hidden container state in the UI layer.
- Any dialog or widget with user-visible text should provide `retranslate_ui()` and respond to `QEvent.LanguageChange`.
- Any dialog that starts a `QTimer` must also own its shutdown in `closeEvent()` so background refresh does not survive window closure.
- Prefer small focused dialogs plus shared widgets over cross-dialog inheritance when scenario and technical flows overlap.

## Boundaries

- `ScenarioWorkflowService` owns scenario preparation and the hidden scenario project container.
- `MLService` and `InferenceHistoryService` own task status, logs, and result metadata.
- UI opens files or exports only after services resolve the canonical path or dataset id.
