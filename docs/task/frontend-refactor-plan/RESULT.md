# Frontend Refactor Plan — Result

## Outcome Summary
A ruthless, high-impact refactor plan has been defined to **eradicate legacy frontend entropy** and replace it with a **feature-first architecture**, a **strict documentation system**, and **CI-enforced quality gates**. The strategy removes dead code, enforces modular boundaries, and mandates i18n-only user-facing text.

## Key Decisions
- **Documentation system overhaul**: `docs/features`, `docs/modules`, `docs/decisions`, and `docs/task` become the authoritative sources. Legacy docs are removed or archived.
- **Feature-based structure**: All user-facing capabilities live under `features/<feature>` with standardized subfolders.
- **No duplicated logic**: APIs consolidated in `services/`, state in feature stores, queries in TanStack composables.
- **Zero tolerance for dead code**: deletion is default; keeping requires justification.

## Deliverables (Planned)
- New `packages/frontend/src/AGENTS.md` (frontend-specific context).
- New docs architecture with migrated and archived content.
- Refactored directory layout and boundary enforcement.
- CI quality gates (lint, unused exports, route coverage, i18n checks, bundle budgets).

## Execution Phases
1. **Audit & Map**: inventory routes, docs, unused files.
2. **Structural Rewrite**: move to target layout, consolidate clients.
3. **Quality Hardening**: enforce boundaries and error/loading patterns.
4. **Legacy Removal**: delete and archive.

## Success Metrics
- 50–70% reduction of unused files.
- New feature shipping time < 1 day.
- Zero raw strings in UI.
- 20% bundle size reduction.
- >70% coverage for business logic.

## Immediate Next Steps
1. Approve scope.
2. Begin docs migration and deletion tagging.
3. Draft `packages/frontend/src/AGENTS.md`.
4. Start Phase 1 audit.
