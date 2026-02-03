# ADR-001: Feature-Based Frontend Architecture

## Status

Accepted

## Context

The frontend codebase was becoming difficult to maintain with a traditional layer-based organization (components/, views/, stores/, etc.). Finding related code required jumping between multiple directories, and feature boundaries were unclear.

Problems with the old structure:

- Scattered code for single features across multiple directories
- Unclear ownership of components and logic
- Difficult to delete unused features
- Hard for new developers to understand the codebase

## Decision

Adopt a **feature-based architecture** where each feature is a self-contained folder with all its code:

```
features/<feature>/
  components/    # Feature-specific components
  pages/         # Route-level pages
  queries/       # TanStack Query hooks
  stores/        # Pinia stores
  index.ts       # Public exports
```

Benefits:

- **Locality of Reasoning**: Everything for a feature is in one place
- **Clear Boundaries**: Features are self-contained and can be understood in isolation
- **Easy Deletion**: Remove a feature by deleting one folder
- **Scalable**: New features follow the same pattern

## Consequences

**Positive**:

- Easier to navigate and understand the codebase
- Clear feature boundaries
- Simpler onboarding for new developers
- Easier to refactor individual features

**Negative**:

- Some code duplication for shared utilities (mitigated by hooks/ and services/)
- Need to be disciplined about not creating cross-feature dependencies

## Related

- Frontend refactor: `docs/task/frontend-refactor-plan/`
- Frontend code: `packages/frontend/src/features/`
- AGENTS.md: `packages/frontend/src/AGENTS.md`
