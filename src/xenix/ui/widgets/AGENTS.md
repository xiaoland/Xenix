# Shared Widget Guidance

## Scope

Adds widget-specific rules for `src/xenix/ui/widgets/`; inherit the parent UI guidance.

## Tripwires

- Keep shared widgets policy-light. Use a narrow option or adapter when one view needs stricter presentation behavior.
- Widgets may own local selection and presentation state, but not services, filesystem business logic, or cross-view workflow.
- Preserve deterministic ordering when returning selected values or rows.
- Move view-specific workflow into the parent dialog or owning service before it expands the shared widget contract.

Verify the focused widget test and the consuming view test for changed behavior.
