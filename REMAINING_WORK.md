# Remaining Work for Full Migration

This document outlines what still needs to be done to complete the monorepo migration.

## Backend - Remaining API Routes

### High Priority Routes

#### 1. Work Items (`/api/work-items/*`)
- [ ] GET `/api/work-items` - List all work items
- [ ] POST `/api/work-items` - Create work item
- [ ] GET `/api/work-items/:id` - Get single work item
- [ ] PUT `/api/work-items/:id` - Update work item
- [ ] DELETE `/api/work-items/:id` - Delete work item

**Source Files**: `server/api/work-items/`

#### 2. Datasets (`/api/data/*`)
- [ ] GET `/api/data` - List datasets
- [ ] POST `/api/data` - Upload dataset
- [ ] GET `/api/data/:id` - Get dataset details
- [ ] DELETE `/api/data/:id` - Delete dataset

**Source Files**: `server/api/data/`

#### 3. Models (`/api/models/*`)
- [ ] GET `/api/models` - List available models
- [ ] GET `/api/models/:id` - Get model details
- [ ] POST `/api/models/sync` - Sync model metadata

**Source Files**: `server/api/models/`

#### 4. Tasks (`/api/tasks/*`)
- [ ] GET `/api/tasks` - List tasks
- [ ] GET `/api/task/:id` - Get task details
- [ ] DELETE `/api/tasks/failed` - Clear failed tasks
- [ ] DELETE `/api/tasks/model` - Delete model tasks

**Source Files**: `server/api/tasks/`, `server/api/task/`

#### 5. Tune Operations (`/api/*-tune`)
- [ ] POST `/api/auto-tune` - Auto hyperparameter tuning
- [ ] POST `/api/manual-tune` - Manual model training

**Source Files**: `server/api/auto-tune.post.ts`, `server/api/manual-tune.post.ts`

#### 6. Predict Operations (`/api/predict/*`)
- [ ] POST `/api/predict` - Generic predict endpoint
- [ ] POST `/api/predict/inline` - Inline prediction
- [ ] POST `/api/predict/by-file` - File-based prediction

**Source Files**: `server/api/predict/`, `server/api/predict.post.ts`

#### 7. Download (`/api/download/*`)
- [ ] GET `/api/download/:id` - Download prediction results

**Source Files**: `server/api/download/`

#### 8. Observation (`/api/obsrv/*`)
- [ ] GET `/api/obsrv/:id` - Get task observation/logs

**Source Files**: `server/api/obsrv/`

### To Remove (Per New Requirement)

#### Python Environment Management
- [ ] DELETE `/api/pythonEnv/status` - Remove
- [ ] DELETE `/api/pythonEnv/setup` - Remove
- [ ] DELETE `/api/pythonEnv/reinstall` - Remove

**Source Files**: `server/api/pythonEnv/` - DELETE ENTIRE DIRECTORY

## Frontend - Remaining Components & Pages

### Pages to Migrate

#### Auth Pages
- [ ] Migrate `app/pages/auth/signin.vue` → `packages/frontend/src/views/auth/SignInView.vue`
- [ ] Migrate `app/pages/auth/signup.vue` → `packages/frontend/src/views/auth/SignUpView.vue`

#### Project Pages
- [ ] Migrate `app/pages/projects/index.vue` → `packages/frontend/src/views/projects/ProjectsView.vue`
- [ ] Migrate `app/pages/projects/[id].vue` → `packages/frontend/src/views/projects/ProjectDetailView.vue`

#### Work Item Pages
- [ ] Create work item management views
- [ ] Prepare data view
- [ ] Tune models view
- [ ] Predict view

#### Dataset Pages
- [ ] Dataset upload view
- [ ] Dataset list view
- [ ] Dataset detail view

### Components to Migrate

Check `app/components/` for existing components:
- [ ] Layout components
- [ ] Form components
- [ ] Table components
- [ ] Model tuning components
- [ ] Prediction components
- [ ] Dataset components

### Services to Migrate

From `app/services/`:
- [ ] `authService.ts` - Authentication API calls
- [ ] `projectService.ts` - Project CRUD
- [ ] `workItemService.ts` - Work item operations
- [ ] `datasetService.ts` - Dataset operations
- [ ] `modelService.ts` - Model operations
- [ ] `taskService.ts` - Task operations
- [ ] `tuneService.ts` - Tuning operations
- [ ] `predictionService.ts` - Prediction operations

**Action**: Update base URL to point to backend server

### Composables to Migrate

From `app/composables/`:
- [ ] `useApi.ts` - API client setup
- [ ] `useFormatters.ts` - Data formatting utilities
- [ ] `useModelTraining.ts` - Model training logic
- [ ] `useDatasetRegistration.ts` - Dataset logic

### Stores to Migrate

From `app/stores/`:
- [ ] `auth.ts` - Authentication state
- [ ] Add project store
- [ ] Add work item store
- [ ] Add dataset store

### UI to Remove (Per New Requirement)

- [ ] Search for and remove all pythonEnv/Python environment management UI
  - Components
  - Pages
  - Store state
  - API service calls

## Configuration & Setup

### Backend
- [ ] Create `.env` file from `.env.example`
- [ ] Setup PostgreSQL database
- [ ] Run migrations: `pnpm db:migrate`
- [ ] Test database connection

### Frontend
- [ ] Configure i18n plugin in `main.ts`
- [ ] Setup API base URL configuration
- [ ] Configure Ant Design Vue theme (if needed)
- [ ] Test dev server: `pnpm dev:frontend`

### Integration
- [ ] Test CORS configuration
- [ ] Test API proxy in Vite
- [ ] Test authentication flow
- [ ] Test file upload/download

## Testing Plan

### Backend Testing
1. Test auth endpoints (signin, signup)
2. Test CRUD operations (projects, work items, datasets)
3. Test ML operations (tune, predict)
4. Test file operations (upload, download)
5. Test background tasks

### Frontend Testing
1. Test routing and navigation
2. Test authentication flow
3. Test form submissions
4. Test data display (tables, charts)
5. Test file uploads
6. Test i18n translations

### Integration Testing
1. Full ML workflow:
   - Upload dataset
   - Create project and work item
   - Prepare data (select features/target)
   - Auto-tune models
   - Compare results
   - Make predictions
2. Test with different model types
3. Test error handling

## Documentation Updates

- [ ] Update main README.md with new structure
- [ ] Update API documentation (docs/api.md)
- [ ] Update development guide (docs/development.md)
- [ ] Update setup guide (docs/setup.md)
- [ ] Create migration guide for contributors

## Deployment Considerations

### Backend Deployment
- [ ] Setup production environment variables
- [ ] Configure production database
- [ ] Setup Python environment on server
- [ ] Configure CORS for production frontend URL
- [ ] Setup process manager (PM2, systemd)

### Frontend Deployment
- [ ] Build for production: `pnpm build:frontend`
- [ ] Configure API URL for production
- [ ] Setup static file hosting (Nginx, CDN)
- [ ] Configure routing (SPA fallback)

## Estimated Effort

| Category | Estimated Time | Priority |
|----------|---------------|----------|
| Backend API routes | 4-6 hours | High |
| Frontend pages | 6-8 hours | High |
| Frontend components | 4-6 hours | High |
| Services & composables | 2-3 hours | Medium |
| Stores | 1-2 hours | Medium |
| Testing | 4-6 hours | High |
| Documentation | 2-3 hours | Medium |
| Remove pythonEnv | 1 hour | High |
| **TOTAL** | **24-35 hours** | - |

## Quick Wins

Start with these to get a working demo quickly:

1. ✅ Phase 1-3 initial setup (DONE)
2. Complete work items API routes (backend)
3. Complete datasets API routes (backend)
4. Migrate auth pages (frontend)
5. Migrate projects list page (frontend)
6. Setup Pinia auth store
7. Test end-to-end auth flow

With these done, you'll have a functional demo showing:
- User can sign in/up
- User can view projects
- Backend and frontend working together

## Notes

- Keep Python ML scripts as-is (they work fine)
- Database schema doesn't need changes
- Focus on web tier (API + UI) migration
- Test incrementally as you migrate each route
