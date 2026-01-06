# Post-Refactor Cleanup Plan

**Date**: January 6, 2026  
**Context**: Following completion of the monorepo refactor (Nuxt.js → Vite+Vue+Hono), this document outlines the systematic cleanup needed to eliminate technical debt and cruft.

---

## Executive Summary

The monorepo refactor successfully migrated Xenix from Nuxt.js full-stack to a modern architecture with separate frontend/backend packages. The migration is **functionally complete** (85/100 score from TODO.md), but several architectural improvements and cleanup tasks remain.

### Current State Analysis

**Strengths:**

- ✅ Monorepo structure established (pnpm workspace)
- ✅ Modern stack (Vite, Vue 3, Hono, Drizzle ORM)
- ✅ TanStack Query implemented in frontend
- ✅ Hono RPC client configured
- ✅ Repository pattern implemented (BaseRepository + 5 specific repos)
- ✅ Error handling with custom error classes
- ✅ Config management with Zod validation
- ✅ BullMQ job queue configured
- ✅ Pino structured logging configured

**Technical Debt:**

- ⚠️ Backend routes have mixed patterns (direct DB access vs repository vs service layer)
- ⚠️ Only 5/10 backend routes use Zod validation
- ⚠️ Service layer incomplete (only ProjectService, WorkItemService implemented)
- ⚠️ Console.log statements still present (though minimal - 0 found in packages)
- ⚠️ Some routes bypass service layer and call repositories directly
- ⚠️ Magic numbers and strings scattered throughout
- ⚠️ Test coverage is minimal (~3 test files per package)
- ⚠️ TODO/FIXME comments exist (5 found)
- ⚠️ Inconsistent logging patterns (logger vs console methods)

---

## Cleanup Strategy

Based on the Post-Refactor Cleanup Checklist, we'll tackle issues in priority order:

### Priority 1: Critical Architecture Cleanup (HIGH IMPACT)

**Goal**: Establish consistent architectural patterns across all code

### Priority 2: Code Quality & Maintainability (MEDIUM IMPACT)

**Goal**: Remove code smells, improve readability, ensure consistency

### Priority 3: Testing & Documentation (FOUNDATIONAL)

**Goal**: Increase confidence in changes, improve onboarding

---

## Detailed Cleanup Tasks

### 1. Dead / Unused Code Removal

#### 1.1 Static Analysis Setup

- [ ] Install and configure ESLint for both backend and frontend
  - Backend: `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`
  - Frontend: `eslint-plugin-vue`, Vue-specific rules
  - Shared: `no-unused-vars`, `no-unreachable`, etc.
- [ ] Run ESLint with `--fix` where safe
- [ ] Document remaining warnings that need manual review

**Estimated findings**: Minimal (modern refactor already fairly clean)

#### 1.2 Unreachable Code Detection

- [ ] Search for unreachable code after returns:
  ```bash
  grep -rn "return" packages/ | grep -A 5 "return" | grep -v "^--$"
  ```
- [ ] Review Python ML scripts for unreachable code

**Expected**: Likely clean due to recent refactor

#### 1.3 Commented Code Cleanup

- [ ] Review files with commented code blocks:
  - `packages/backend/src/utils/pythonExecutor.ts`
  - `packages/backend/src/utils/syncModels.ts`
  - `packages/backend/src/middleware/auth.ts`
  - Frontend components with comments
- [ ] Decision: Delete or document why preserved
- [ ] Create rule: No commented code without `// ARCHIVE:` prefix + reason

**Files to review**: ~20 files identified with comment blocks

#### 1.4 Debug/Scaffolding Cleanup

- [x] Remove console.log statements (DONE - 0 found in packages)
- [ ] Audit logger usage - ensure consistency:
  - Replace any remaining console._ with logger._
  - Ensure log levels are appropriate (info, warn, error)
- [ ] Review TODO/FIXME comments:
  - `packages/backend/src/routes/predict.ts:1` - "TODO: by-file and generic predict endpoints"
  - `packages/frontend/src/components/ml/tuning/TuningStep.vue:1` - "TODO: implement delete failed tasks"
  - `packages/frontend/src/views/projects/ProjectDetailView.vue:1` - "TODO: Migrate project detail"
  - `packages/frontend/src/views/projects/ProjectsView.vue:1` - "TODO: Migrate projects list"
  - `packages/frontend/src/views/tasks/TasksView.vue:1` - "TODO: Create useTaskLogs composable"
- [ ] Either resolve TODOs or create GitHub issues and reference them

**Action items**: 5 TODOs to resolve or track

---

### 2. Duplicated Code Elimination

#### 2.1 Backend Route Patterns

**Issue**: Routes use mixed patterns for data access

**Current patterns found:**

1. Direct DB access: `datasets.ts`, `tasks.ts`, `obsrv.ts`, `download.ts`
2. Repository access: `projects.ts` (partial)
3. Service access: `work-items.ts` (partial), `projects.ts` (partial)

**Action plan:**

- [ ] Complete service layer implementation:
  - [ ] `DatasetService.ts` - CRUD for datasets
  - [ ] `TaskService.ts` - Task monitoring and updates
  - [ ] `AuthService.ts` - Authentication logic
  - [ ] `PredictionService.ts` - Prediction operations
  - [ ] `TuneService.ts` - Model tuning operations
- [ ] Refactor all routes to use service layer:
  - [ ] `datasets.ts` → use DatasetService
  - [ ] `tasks.ts` → use TaskService
  - [ ] `auth.ts` → use AuthService
  - [ ] `predict.ts` → use PredictionService
  - [ ] `tune.ts` → use TuneService
  - [ ] `download.ts` → use appropriate service
  - [ ] `models.ts` → use ModelService
  - [ ] `obsrv.ts` → use TaskService or ObservationService
- [ ] Create pattern documentation: `docs/backend-patterns.md`

**Files to refactor**: 8-10 route files

#### 2.2 Frontend Data Fetching Patterns

**Status**: ✅ Already modernized with TanStack Query composables

**No action needed** - Views already use:

- `useProjects()`, `useWorkItems()`, `useDatasets()`, `useTasks()`, `useFormatters()`

#### 2.3 Configuration & Constants

- [ ] Audit for hardcoded values:
  ```bash
  grep -rn '"http://\|3000\|3001\|5173"' packages/
  ```
- [ ] Extract to environment variables or config files:
  - Port numbers
  - API URLs
  - File paths
  - Timeouts
- [ ] Document in `.env.example` files

**Expected**: Some hardcoded ports and paths to extract

#### 2.4 Shared Utilities

- [ ] Look for similar utility functions across packages
- [ ] Extract common logic to `packages/shared/src/utils/`
- [ ] Candidates:
  - Date formatting (already in `useFormatters`)
  - Validation helpers
  - File handling utilities

**Expected**: Minimal duplication (shared package exists)

---

### 3. Legacy / Obsolete Code Cleanup

#### 3.1 Backend Services Completion

**Current state**: Only 2/5 services implemented

- [ ] Review backend service implementations:
  - ✅ `ProjectService.ts` - implemented
  - ✅ `WorkItemService.ts` - implemented
  - ❌ `DatasetService.ts` - stub only
  - ❌ `TaskService.ts` - stub only
  - ❌ `ModelService.ts` - stub only
- [ ] Complete or remove stubs
- [ ] Ensure all services follow consistent pattern:

  ```typescript
  export class XxxService {
    constructor(private repo: XxxRepository) {}

    async create(data: CreateXxxDto): Promise<Xxx> { ... }
    async findById(id: number): Promise<Xxx | null> { ... }
    async update(id: number, data: UpdateXxxDto): Promise<Xxx> { ... }
    async delete(id: number): Promise<void> { ... }
  }
  ```

**Files to complete**: 3 service stubs

#### 3.2 Frontend Legacy Patterns

**Status**: ✅ Frontend already modernized - services directory removed

**No action needed**

#### 3.3 Python Integration Review

- [ ] Review `packages/backend/src/utils/pythonExecutor.ts` (295 lines):
  - Check for old workarounds no longer needed
  - Verify error handling is robust
  - Ensure process management is clean
- [ ] Review Python ML scripts in `packages/backend/src/business/ml/regression/`:
  - Remove any deprecated scikit-learn patterns
  - Check for Python 2 compatibility code (if any)

**Files to review**: ~10-15 Python files + executor

#### 3.4 Deprecated API Usage

- [ ] Check for deprecated npm package usage:
  ```bash
  npm outdated
  ```
- [ ] Review dependencies for deprecation warnings
- [ ] Update or replace deprecated packages

---

### 4. Code Smells and Structural Improvements

#### 4.1 Long Methods/Classes

**Target**: Functions > 50 lines, classes > 200 lines

**Files identified:**

- `packages/frontend/src/components/ml/tuning/TuningStep.vue` (372 lines)
- `packages/frontend/src/components/ml/prediction/PredictionStep.vue` (327 lines)
- `packages/backend/src/utils/pythonExecutor.ts` (295 lines)
- `packages/frontend/src/components/ml/prediction/PredictionResult.vue` (276 lines)
- `packages/frontend/src/views/tasks/TasksView.vue` (252 lines)
- `packages/backend/src/business/ml/index.ts` (227 lines)

**Action plan:**

- [ ] Review each large file for Single Responsibility violations
- [ ] Extract reusable components/functions:
  - TuningStep → extract parameter form, model selection, task display
  - PredictionStep → extract file upload, model selection, result display
  - pythonExecutor → extract process management, error handling
  - PredictionResult → extract chart components, metrics display
- [ ] Document refactoring decisions

**Files to refactor**: 6 large files

#### 4.2 Magic Numbers/Strings

- [ ] Search for magic values:
  ```bash
  grep -rn '"[0-9]\{3,\}"' packages/
  grep -rn '(?<![a-zA-Z_])[0-9]{4,}(?![a-zA-Z_])' packages/
  ```
- [ ] Extract to named constants:
  - HTTP status codes → use Hono's status helpers
  - Timeouts → environment variables or config
  - Batch sizes → constants file
- [ ] Create `packages/shared/src/constants/` for shared values

**Expected**: Moderate findings (ports, timeouts, batch sizes)

#### 4.3 Deep Nesting

- [ ] Identify deeply nested code (>3 levels):
  ```bash
  # Check indentation levels
  awk '{ match($0, /^[ \t]*/); indent = RLENGTH; if (indent > 12) print FILENAME ":" NR ":" indent }' packages/**/*.ts
  ```
- [ ] Apply refactoring:
  - Early returns / guard clauses
  - Extract methods
  - Invert conditionals

**Expected**: Moderate findings in route handlers and Vue components

#### 4.4 Code Formatting

- [ ] Install Prettier:
  ```bash
  pnpm add -D prettier @trivago/prettier-plugin-sort-imports
  ```
- [ ] Create `.prettierrc.json`:
  ```json
  {
    "semi": true,
    "singleQuote": true,
    "trailingComma": "es5",
    "printWidth": 80,
    "tabWidth": 2
  }
  ```
- [ ] Run Prettier on entire codebase:
  ```bash
  pnpm prettier --write "packages/**/*.{ts,vue,json}"
  ```
- [ ] Add to package.json scripts: `"format": "prettier --write ."`

#### 4.5 Naming Consistency

- [ ] Review naming conventions:
  - Routes: kebab-case URLs (✅ already consistent)
  - Variables: camelCase (audit needed)
  - Types: PascalCase (✅ already consistent)
  - Files: match export (audit needed)
- [ ] Create naming guide: `docs/naming-conventions.md`

---

### 5. Documentation and Comments

#### 5.1 Outdated Comments

- [ ] Find comments referencing old architecture:
  ```bash
  grep -rni "nuxt\|nitro\|pages/\|composable" packages/ --include="*.ts" --include="*.vue"
  ```
- [ ] Remove or update comments to reflect current architecture

**Expected**: Likely clean (recent refactor)

#### 5.2 Missing Documentation

- [ ] Add JSDoc comments to public APIs:
  - All service methods
  - All repository methods
  - All exported utilities
- [ ] Create interface documentation:
  - `docs/api/README.md` - API endpoint listing
  - `docs/architecture/services.md` - Service layer guide
  - `docs/architecture/repositories.md` - Repository pattern guide

#### 5.3 Redundant Comments

- [ ] Remove obvious comments like:
  ```typescript
  // Get user by ID
  const user = getUserById(id);
  ```
- [ ] Keep only non-obvious explanations:
  ```typescript
  // Using OR condition because users can sign in with email or phone
  const user = await db.select()...
  ```

---

### 6. Dependencies and Imports

#### 6.1 Unused Imports Detection

- [ ] Enable ESLint rule: `@typescript-eslint/no-unused-vars`
- [ ] Run and fix:
  ```bash
  pnpm eslint --fix packages/
  ```
- [ ] Manual review remaining warnings

#### 6.2 Dependency Audit

- [ ] Check for unused packages:
  ```bash
  pnpm exec depcheck
  ```
- [ ] Review each package.json:
  - `packages/backend/package.json`
  - `packages/frontend/package.json`
  - `packages/shared/package.json`
- [ ] Remove unused dependencies
- [ ] Check for duplicate dependencies across packages

**Expected**: Some dev dependencies may be unused

#### 6.3 Dependency Updates

- [ ] Check outdated packages:
  ```bash
  pnpm outdated
  ```
- [ ] Update patch versions (safe):
  ```bash
  pnpm update --latest
  ```
- [ ] Review and plan major version updates (breaking changes)

---

### 7. Testing and Safety Checks

#### 7.1 Current Test Status

**Existing tests:**

- Backend: `datasetUtils.test.ts` (1 file)
- Frontend: `auth.test.ts` (1 file)
- Shared: `dataset.test.ts`, `project.test.ts` (2 files)

**Coverage**: Estimated <10%

#### 7.2 Test Expansion Plan

- [ ] Backend unit tests:
  - [ ] Repository tests (5 repositories × 4 methods = 20 tests)
  - [ ] Service tests (5 services × 4 methods = 20 tests)
  - [ ] Utility tests (datasetUtils, taskUtils, pythonExecutor)
- [ ] Backend integration tests:
  - [ ] Route tests for each endpoint (10 routes × 2 tests = 20 tests)
  - [ ] Authentication flow tests
  - [ ] ML workflow end-to-end tests
- [ ] Frontend unit tests:
  - [ ] Composable tests (5 composables × 3 tests = 15 tests)
  - [ ] Store tests (auth store)
  - [ ] Utility tests (formatters)
- [ ] Frontend component tests:
  - [ ] Test major components (10 components × 2 tests = 20 tests)

**Target**: 60% coverage minimum

#### 7.3 Test Infrastructure

- [ ] Configure test coverage thresholds in `vitest.config.ts`:
  ```typescript
  coverage: {
    provider: 'v8',
    reporter: ['text', 'html', 'lcov'],
    exclude: ['**/*.test.ts', '**/node_modules/**'],
    lines: 60,
    functions: 60,
    branches: 60,
    statements: 60
  }
  ```
- [ ] Add coverage reports to CI/CD (if exists)
- [ ] Create test data fixtures

#### 7.4 Smoke Tests

- [ ] Create smoke test suite:
  - [ ] Backend server starts
  - [ ] Database connection works
  - [ ] Redis connection works (when BullMQ enabled)
  - [ ] Frontend builds successfully
  - [ ] All routes return valid responses
- [ ] Add to pre-deployment checklist

---

### 8. Final Validation

#### 8.1 Build Validation

- [ ] Clean build test:
  ```bash
  rm -rf packages/*/dist packages/*/node_modules
  pnpm install
  pnpm build
  ```
- [ ] Check for build warnings
- [ ] Verify output bundle sizes

#### 8.2 Type Safety Validation

- [ ] Run TypeScript compilation:
  ```bash
  pnpm -r exec tsc --noEmit
  ```
- [ ] Ensure 0 type errors
- [ ] Review any `@ts-ignore` comments and remove if possible

#### 8.3 Linting Validation

- [ ] Run all linters:
  ```bash
  pnpm eslint .
  pnpm prettier --check .
  ```
- [ ] Achieve 0 errors (warnings acceptable with justification)

#### 8.4 Manual Testing

- [ ] Test ML workflow end-to-end:
  - [ ] Sign up / sign in
  - [ ] Create project
  - [ ] Upload dataset
  - [ ] Create work item (Prepare step)
  - [ ] Tune models (Auto + Manual)
  - [ ] Predict with trained model
  - [ ] Download results
- [ ] Test error scenarios:
  - [ ] Invalid credentials
  - [ ] Missing file
  - [ ] Invalid model parameters
  - [ ] Unauthorized access

#### 8.5 Code Review

- [ ] Conduct team code review focusing on:
  - Architectural consistency
  - Naming clarity
  - Error handling completeness
  - Security considerations
- [ ] Document decisions in `docs/adr/` (Architecture Decision Records)

#### 8.6 Performance Check

- [ ] Run frontend in production mode:
  ```bash
  pnpm build:frontend
  pnpm preview:frontend
  ```
- [ ] Check bundle size:
  ```bash
  du -sh packages/frontend/dist
  ```
- [ ] Verify initial load time < 3s
- [ ] Check backend memory usage under load

---

## Implementation Timeline

### Week 1: Critical Architecture (Priority 1)

- Day 1-2: Complete service layer (DatasetService, TaskService, AuthService)
- Day 3-4: Refactor routes to use service layer consistently
- Day 5: Apply Zod validation to all 10 routes

**Deliverable**: Consistent 3-layer architecture (routes → services → repositories)

### Week 2: Code Quality (Priority 2)

- Day 1: Install and configure ESLint + Prettier
- Day 2: Run automated fixes, review warnings
- Day 3: Refactor large files (6 identified)
- Day 4: Extract magic numbers, improve naming
- Day 5: Clean up comments and documentation

**Deliverable**: Clean, readable, consistent codebase

### Week 3: Testing (Priority 3)

- Day 1-2: Write service tests (5 services)
- Day 3-4: Write route integration tests (10 routes)
- Day 5: Write frontend composable tests (5 composables)

**Deliverable**: 60%+ test coverage

### Week 4: Final Validation

- Day 1: Full build and lint validation
- Day 2: Manual end-to-end testing
- Day 3: Performance testing and optimization
- Day 4: Documentation review and updates
- Day 5: Team code review and sign-off

**Deliverable**: Production-ready, maintainable codebase

---

## Success Metrics

### Before Cleanup (Current State)

- **Refactor Score**: 85/100
- **Test Coverage**: <10%
- **Code Consistency**: Mixed (3 patterns for data access)
- **Type Safety**: Partial (5/10 routes validated)
- **Documentation**: Good (refactor docs complete)
- **Maintainability**: Fair (some technical debt)

### After Cleanup (Target State)

- **Refactor Score**: 95/100
- **Test Coverage**: >60%
- **Code Consistency**: Excellent (single pattern throughout)
- **Type Safety**: Complete (all routes validated)
- **Documentation**: Excellent (API docs + architecture guides)
- **Maintainability**: Excellent (clean, tested, documented)

### Key Performance Indicators

- ✅ 0 TypeScript compilation errors
- ✅ 0 ESLint errors (warnings allowed with justification)
- ✅ 10/10 routes use Zod validation
- ✅ 10/10 routes use service layer
- ✅ 5/5 services fully implemented
- ✅ Test coverage >60%
- ✅ Build time <30 seconds
- ✅ Frontend bundle size <500KB gzipped
- ✅ All manual workflows functional

---

## Risk Assessment

### Low Risk

- **ESLint/Prettier setup**: Automated, safe
- **Formatting**: Automated, reversible
- **Documentation**: Additive, no code changes

### Medium Risk

- **Service layer completion**: New code, needs testing
- **Route refactoring**: Existing functionality, comprehensive testing needed
- **Large file refactoring**: Risk of breaking functionality

### High Risk

- **Dependency updates**: Potential breaking changes
- **Python executor changes**: Critical ML functionality

### Mitigation Strategies

1. **Make incremental changes**: Commit after each logical unit
2. **Test thoroughly**: Run tests after each change
3. **Manual validation**: Test ML workflow after backend changes
4. **Version control**: Use feature branches, code reviews
5. **Rollback plan**: Keep previous working commits tagged

---

## Conclusion

This cleanup plan systematically addresses technical debt accumulated during the monorepo refactor while building upon the solid foundation already established. By following this plan, we will achieve:

1. **Architectural consistency**: Single pattern (routes → services → repositories)
2. **Type safety**: Zod validation on all inputs
3. **Maintainability**: Clean, tested, documented code
4. **Developer experience**: Clear patterns, good tooling
5. **Production readiness**: Robust, performant, reliable

The cleanup is estimated to take 4 weeks with 1 developer, or 2 weeks with 2 developers working in parallel. The investment will pay dividends in reduced bugs, faster feature development, and easier onboarding of new team members.

---

## Appendix: Tools Reference

### Static Analysis Tools

- **ESLint**: `@typescript-eslint/eslint-plugin` + `eslint-plugin-vue`
- **Prettier**: Code formatting
- **depcheck**: Unused dependency detection
- **TypeScript**: Type checking with `--noEmit`

### Testing Tools

- **Vitest**: Unit and integration testing
- **@vue/test-utils**: Vue component testing
- **supertest**: HTTP endpoint testing (optional)

### Development Tools

- **tsx**: TypeScript execution for development
- **pnpm**: Fast, efficient package manager
- **Drizzle Kit**: Database migrations

### Monitoring Tools

- **pnpm outdated**: Check for dependency updates
- **du**: Check bundle sizes
- **Vite bundle analyzer**: Frontend bundle analysis

---

**Status**: Plan created, ready for implementation  
**Next Step**: Begin Week 1 - Critical Architecture cleanup
