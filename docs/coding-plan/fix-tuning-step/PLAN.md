# Fix TuningStep Issues - Implementation Plan

## Overview
Fix critical issues in TuningStep component to improve user experience and functionality:
1. Add manual tune button with parameter editing dialog
2. Fix step navigation bug by implementing custom Steps component
3. Display metrics properly and allow viewing parameters

## Reference Commits
- Using examples from commit `9fdcacdee415f6e5b6cc50c298ecd1ebd28b2781`
  - ManualTuneDialog.vue - Single train dialog with parameter editing
  - Steps.vue - Custom steps component (to replace ant-design buggy steps)
  - ModelTuningSubRow.vue - Metrics display and params viewing

## Issues to Fix

### Issue 1: Manual Tune Button Missing
**Current State:**
- TuningStep only has auto-tune button
- Users cannot manually tune a single model with custom parameters

**Target State:**
- Add "Manual Tune" button next to auto-tune button
- Button opens SingleTrain dialog
- Dialog allows users to:
  - Select a single model
  - Edit model parameters via form
  - Submit single training task

**Components to Create:**
- `ManualTuneDialog.vue` - Dialog for manual model tuning
- `ModelParamForm.vue` - Form for editing model parameters (if not exists)

### Issue 2: Step Navigation Bug
**Current State:**
- Using ant-design `<a-steps>` component
- Continue button doesn't advance to step 3 (PredictionStep)
- Likely ant-design bug with step state management

**Target State:**
- Replace ant-design steps with custom Steps component
- Custom component has full control over step rendering
- No dependency on buggy ant-design steps behavior

**Components to Create:**
- `packages/frontend/src/components/common/Steps.vue` - Custom steps component

**Components to Update:**
- `WorkItemDetailView.vue` - Replace `<a-steps>` with custom `<Steps>`

### Issue 3: Metrics Not Displaying + No View Params
**Current State:**
- TuningStep shows minimal metrics in table
- No way to view full parameters of completed tasks
- Missing detailed metrics display

**Target State:**
- Display comprehensive metrics for each task
- Add "View Params" button for completed tasks
- Show task type (auto-tune vs manual-tune)
- Better visual presentation of metrics

**Components to Update:**
- `TuningStep.vue` - Enhance table to show:
  - Task type tags (auto/manual)
  - Comprehensive metrics
  - View params button
  - View logs button (if needed)

**Components to Create (if needed):**
- `ModelAutoMetrics.vue` - Component for displaying metrics
- Parameter viewing modal/dialog

## Implementation Steps

### Step 1: Create Custom Steps Component
```
packages/frontend/src/components/common/Steps.vue
```
- Copy from reference commit
- Adapt styling to current theme
- Support: current prop, items array with title/description
- Visual states: completed, active, pending
- Connector lines between steps

### Step 2: Update WorkItemDetailView to Use Custom Steps
```
packages/frontend/src/views/work-items/WorkItemDetailView.vue
```
- Import custom Steps component
- Replace `<a-steps>` with custom `<Steps>`
- Pass proper props: `:current="currentStep"` and `:items="stepItems"`
- Define stepItems array with i18n translations

### Step 3: Create ModelParamForm Component
```
packages/frontend/src/components/ml/tuning/ModelParamForm.vue
```
- Form to edit model parameters
- Load parameter schema from model definition
- Support different input types (number, select, etc.)
- Validation

### Step 4: Create ManualTuneDialog Component
```
packages/frontend/src/components/ml/tuning/ManualTuneDialog.vue
```
- Modal dialog for manual tuning
- Model selection dropdown
- ModelParamForm for parameter editing
- Submit to create manual-tune task
- Cancel/confirm buttons

### Step 5: Update TuningStep with Manual Tune Button
```
packages/frontend/src/components/ml/tuning/TuningStep.vue
```
- Add "Manual Tune" button next to auto-tune
- Wire up to open ManualTuneDialog
- Handle dialog submission
- Refresh tasks after manual tune starts

### Step 6: Enhance TuningStep Metrics Display
```
packages/frontend/src/components/ml/tuning/TuningStep.vue
```
- Update table columns to show more metrics
- Add task type column with tags (auto/manual)
- Add "View Params" button in action column
- Create params viewing modal
- Display comprehensive metrics (R², RMSE, MAE, etc.)

### Step 7: Create Supporting Components
If needed:
- `ModelAutoMetrics.vue` - Display metrics in formatted way
- Parameter viewing modal component

### Step 8: API Integration
Ensure proper API calls for:
- Manual tune submission: `POST /api/tune/manual-tune`
- Fetching task details with params
- Loading model parameter schemas

### Step 9: I18n Translations
Add necessary translations for:
- Manual tune button and dialog
- Step titles/descriptions for custom Steps
- Metrics labels
- View params button

## Files to Create
1. `packages/frontend/src/components/common/Steps.vue`
2. `packages/frontend/src/components/ml/tuning/ManualTuneDialog.vue`
3. `packages/frontend/src/components/ml/tuning/ModelParamForm.vue` (if not exists)
4. `packages/frontend/src/components/ml/tuning/ModelAutoMetrics.vue` (if needed)

## Files to Modify
1. `packages/frontend/src/views/work-items/WorkItemDetailView.vue`
2. `packages/frontend/src/components/ml/tuning/TuningStep.vue`
3. I18n translation files (if applicable)

## Testing Checklist
- [ ] Manual tune button appears and opens dialog
- [ ] Dialog allows selecting model and editing params
- [ ] Manual tune task is created successfully
- [ ] Custom Steps component displays correctly
- [ ] Step navigation works properly (0 → 1 → 2)
- [ ] Metrics display comprehensively in table
- [ ] View params button shows full parameters
- [ ] Task type tags display correctly
- [ ] All translations work

## Notes
- Delete and refactor ruthlessly - no backward compatibility needed
- Use examples from commit 9fdcacdee415f6e5b6cc50c298ecd1ebd28b2781
- Focus on clean, working implementation
- Ensure proper TypeScript typing
