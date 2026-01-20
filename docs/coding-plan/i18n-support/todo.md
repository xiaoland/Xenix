# i18n Implementation TODO

This document tracks the progress of replacing hard-coded strings with i18n translations across the frontend.

## Progress Overview

- [x] Core infrastructure (i18n setup, remote loading)
- [x] Layout components (DefaultLayout, LanguageSwitcher)
- [x] HomeView
- [x] Auth views (SignIn, SignUp)
- [x] Work Item views (New, Detail)
- [x] Datasets view (has hard-coded "No datasets yet" in empty state)
- [x] Tasks view
- [x] Components (Project components done, Dataset components mostly done, ML components mostly done)

## Files to Update

### Views

#### Auth Views

- [x] `src/views/auth/SignInView.vue`
  - [x] Page title "Sign In"
  - [x] Subtitle "ML Training Platform"
  - [x] Form labels and placeholders
  - [x] Button text
  - [x] Error/success messages
  - [x] "Don't have an account?" link text
  - [x] Validation messages

- [x] `src/views/auth/SignUpView.vue`
  - [x] Page title "Sign Up"
  - [x] Form labels and placeholders
  - [x] Button text
  - [x] Error/success messages
  - [x] "Already have an account?" link text
  - [x] Validation messages

#### Work Item Views

- [x] `src/views/work-items/WorkItemNewView.vue`
  - [x] Card title "Create New Work Item"
  - [x] Form labels and placeholders
  - [x] Button text
  - [x] Success/error messages

- [x] `src/views/work-items/WorkItemDetailView.vue`
  - [x] "Work Item Not Found" title
  - [x] Steps labels (Prepare, Tune, Predict)
  - [x] Step descriptions
  - [x] All user-facing text

#### Dataset View

- [x] `src/views/datasets/DatasetsView.vue`
  - [x] Page title
  - [x] Upload modal title
  - [x] Form labels and placeholders
  - [ ] Empty state message (hard-coded "No datasets yet")
  - [x] Success/error messages
  - [x] Delete confirmation dialog

#### Tasks View

- [x] `src/views/tasks/TasksView.vue`
  - [x] Page title "Task Logs"
  - [x] Table headers
  - [x] Filter labels
  - [x] All user-facing text

### Components

#### Project Components

- [x] `src/components/project/ProjectFormModal.vue`
  - [x] Modal title
  - [x] Form labels and placeholders
  - [x] Button text

- [x] `src/components/project/ProjectCard.vue`
  - [x] Action button text
  - [ ] Labels and tooltips (status labels hard-coded: "active", "completed", "archived")

- [x] `src/components/project/WorkItemRow.vue`
  - [ ] Status labels (hard-coded: 'active', 'completed', 'archived')

#### Dataset Components

- [x] `src/components/dataset/DatasetSelector.vue`
  - [x] Selector label
  - [ ] Placeholder text (hard-coded "No datasets found")
  - [x] Empty state message
  - [x] Validation messages

- [x] `src/components/dataset/DatasetUpload.vue`
  - [x] Upload instructions
  - [x] File type hints
  - [x] Error messages

#### ML Components

- [x] `src/components/ml/prepare/PrepareStep.vue`
  - [x] Step instructions
  - [x] Button labels
  - [x] Validation messages

- [x] `src/components/ml/prepare/ColumnSelector.vue`
  - [x] Column selection labels
  - [x] Instructions
  - [x] Validation messages

- [x] `src/components/ml/tuning/TuningStep.vue`
  - [x] Model selection labels
  - [x] Tuning options
  - [x] Status messages
  - [x] Button text

- [x] `src/components/ml/prediction/PredictionStep.vue`
  - [x] Upload instructions
  - [ ] Mode selection labels (hard-coded "Upload Prediction Data")
  - [x] Button text
  - [x] Status messages

- [x] `src/components/ml/prediction/PredictionResult.vue`
  - [x] Result labels
  - [x] Download button text
  - [x] Status messages

## Translation Keys Structure

Organize translation keys by feature/module:

```
{
  "auth": {
    "signin": { ... },
    "signup": { ... }
  },
  "workItems": {
    "new": { ... },
    "detail": { ... }
  },
  "datasets": { ... },
  "tasks": { ... },
  "components": {
    "project": { ... },
    "dataset": { ... },
    "ml": { ... }
  }
}
```

## Remaining Hard-coded Strings

- `src/views/datasets/DatasetsView.vue`: "No datasets yet" in a-empty description
- `src/components/dataset/DatasetSelector.vue`: "No datasets found" in a-empty description
- `src/components/ml/prediction/PredictionStep.vue`: "Upload Prediction Data" in h3
- `src/components/project/ProjectCard.vue`: Status values "active", "completed", "archived"
- `src/components/project/WorkItemRow.vue`: Status values 'active', 'completed', 'archived'
- `src/views/work-items/WorkItemDetailView.vue`: Status display (may need translation for status values)

## Notes

- Ensure all validation messages use i18n
- Replace console.log messages that users see
- Update success/error toast messages
- Check for hard-coded strings in computed properties
- Test language switching on all updated pages
- Run `pnpm run i18n:check` after updates to verify coverage
- Fix remaining hard-coded strings listed above
