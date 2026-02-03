# Frontend Refactor Plan (Ruthless & Revolutionary)

## 0. Purpose
Deliver a decisive, zero-legacy, maintainable frontend by **eliminating dead code, consolidating architecture, and enforcing documentation/engineering discipline**. This plan prioritizes **clarity, speed, and long-term sustainability** over compatibility with outdated patterns.

## 1. North-Star Principles (Non-negotiable)
1. **Delete > Fix**: If a file/feature is unused or not shipping value within 30 days, delete it.
2. **Single Source of Truth**: No duplicate docs, types, or business logic across layers.
3. **Locality of Reasoning**: Each feature is a folder with everything you need to understand and maintain it.
4. **Predictable Layout**: Standardized structure, enforced through linting and CI.
5. **No Hidden Magic**: No global side effects; only explicit imports/initialization.

## 2. Documentation Revolution
### 2.1 New Docs Architecture
Adopt and enforce the user-proposed structure (features/modules/decisions), plus task outputs in `docs/task`:

```
docs/
  features/
    <feature-name>/
      PRD.md
      HLD.md
      LLD.md
  modules/
    <module-name>.md
  decisions/
    001-<decision-title>.md
  task/
    <task-name>/
      PLAN.md
      RESULT.md
src/
  AGENTS.md
```

### 2.2 Documentation Rules
- Feature docs reference module docs instead of repeating details.
- Only maintain:
  - Project constraints (tech stack, structure, conventions).
  - ADRs (append-only).
  - PRDs (archived after release).
- **Delete** outdated, redundant, or abandoned documents.
- Create `packages/frontend/src/AGENTS.md` (frontend-specific) with:
  - Tech stack
  - Directory structure
  - Coding conventions
  - Current state

### 2.3 Docs Migration Plan
- Inventory all docs under `packages/frontend` and `docs/`.
- Tag each doc: `KEEP`, `MERGE`, `ARCHIVE`, `DELETE`.
- Migrate surviving docs into new structure.
- Archive deprecated PRDs under `docs/features/<feature>/PRD.md` with `status: archived`.

## 3. Codebase Restructure
### 3.1 Target Frontend Layout (Vite + Vue 3)
```
packages/frontend/src/
  app/                # app bootstrapping, routers, global providers
  assets/             # static assets
  components/         # shared generic UI components
  features/           # feature modules (route-level, state, API)
  hooks/              # composables
  layouts/            # layout components
  locales/            # i18n resources
  routes/             # route definitions
  services/           # API clients, SDK wrappers
  styles/             # global styles, UnoCSS config
  types/              # local-only types (shared types go to @xenix/shared)
  utils/              # pure utilities
```

### 3.2 Feature Folder Standard
Each feature contains **everything** it needs (routes, views, components, state, queries):
```
features/<feature>/
  api/
  components/
  pages/
  queries/
  stores/
  types/
  index.ts
```

### 3.3 Zero-Tolerance Rules
- **No dead pages or routes** (enforced by route index audit).
- **No duplicated API clients**; must live under `services/`.
- **No direct API calls in components**; use TanStack Query composables.
- **No hard-coded user-facing strings**; i18n only.

## 4. Cleanup & Deletion Sprint
### 4.1 Inventory & Deletion (Week 1)
- Identify and remove:
  - Unused components
  - Abandoned features
  - Legacy CSS/SCSS files
  - Dead API clients
  - Obsolete routes

### 4.2 Dependency Purge
- Remove unused packages (run `pnpm -r why <pkg>`).
- Lock versions, reduce plugins, avoid “tooling for tooling’s sake”.

## 5. Refactor Phases
### Phase 1 — Audit & Map (1 week)
- Build a **feature map** (routes → feature folders → business owners).
- Establish `docs/modules` and initial ADRs.
- Snapshot current state (screens, routes, API endpoints).

### Phase 2 — Structural Rewrite (2–3 weeks)
- Migrate to target layout.
- Move all route definitions to `routes/` and assemble lazily.
- Move state management into feature modules.
- Consolidate API clients.

### Phase 3 — Quality Hardening (2 weeks)
- Enforce lint rules and folder boundaries.
- Add query/data layer guidelines.
- Implement error boundaries and global empty/error/loading states.

### Phase 4 — Legacy Removal (1 week)
- Delete abandoned features and dead code.
- Archive old PRDs and docs.

## 6. Quality Gates (CI Enforced)
- **ESLint + TypeScript strict mode**
- **Route coverage check**: all routes map to features
- **Unused export checks** (TS/ESLint rules)
- **i18n completeness** (no raw user strings)
- **Bundle size budgets**

## 7. Migration Rules
- Each PR migrates **one feature** and its docs.
- No partial migrations; each feature folder must compile and run.
- Every migration PR must include: updated PRD, architecture references, ADRs if needed.

## 8. Team Workflow (New Discipline)
```
产品层：写/更新 PRD
    ↓
确定涉及哪些代码库
    ↓
对每个代码库：
    PRD + 该库的 AGENTS.md → 跟 Agent 对话 → 代码
```

## 9. Deliverables
- `packages/frontend/src/AGENTS.md`
- New docs architecture fully populated
- Feature-based directory refactor
- CI rules for architecture boundaries
- Dependency list minimized

## 10. Success Metrics
- 50–70% reduction in unused files
- New feature shipped in < 1 day
- Zero raw strings in UI
- Bundle size reduced by 20%
- Code coverage > 70% for business logic

## 11. Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Large refactor destabilizes | Feature-by-feature PRs + smoke tests |
| Incomplete knowledge of legacy | Capture route map before deleting |
| Slowed velocity | Time-box migrations and use templates |

## 12. Immediate Next Actions (Week 0)
1. Approve this plan and task scope.
2. Start docs migration and inventory deletion candidates.
3. Build `packages/frontend/src/AGENTS.md` draft.
4. Kick off Phase 1 audit.
