# i18n Implementation TODO

This document tracks the progress of replacing hard-coded strings with i18n translations across the frontend.

## Progress Overview

- [x] Core infrastructure (i18n setup, remote loading)
- [x] Layout components (DefaultLayout, LanguageSwitcher)
- [x] HomeView
- [ ] Auth views (SignIn, SignUp)
- [ ] Work Item views (New, Detail)
- [ ] Datasets view
- [ ] Tasks view
- [ ] Components (Project, Dataset, ML components)

## Files to Update

### Views

#### Auth Views
- [ ] `src/views/auth/SignInView.vue`
  - [ ] Page title "Sign In"
  - [ ] Subtitle "ML Training Platform"
  - [ ] Form labels and placeholders
  - [ ] Button text
  - [ ] Error/success messages
  - [ ] "Don't have an account?" link text
  - [ ] Validation messages

- [ ] `src/views/auth/SignUpView.vue`
  - [ ] Page title "Sign Up"
  - [ ] Form labels and placeholders
  - [ ] Button text
  - [ ] Error/success messages
  - [ ] "Already have an account?" link text
  - [ ] Validation messages

#### Work Item Views
- [ ] `src/views/work-items/WorkItemNewView.vue`
  - [ ] Card title "Create New Work Item"
  - [ ] Form labels and placeholders
  - [ ] Button text
  - [ ] Success/error messages

- [ ] `src/views/work-items/WorkItemDetailView.vue`
  - [ ] "Work Item Not Found" title
  - [ ] Steps labels (Prepare, Tune, Predict)
  - [ ] Step descriptions
  - [ ] All user-facing text

#### Dataset View
- [ ] `src/views/datasets/DatasetsView.vue`
  - [ ] Page title
  - [ ] Upload modal title
  - [ ] Form labels and placeholders
  - [ ] Empty state message
  - [ ] Success/error messages
  - [ ] Delete confirmation dialog

#### Tasks View
- [ ] `src/views/tasks/TasksView.vue`
  - [ ] Page title "Task Logs"
  - [ ] Table headers
  - [ ] Filter labels
  - [ ] All user-facing text

### Components

#### Project Components
- [ ] `src/components/project/ProjectFormModal.vue`
  - [ ] Modal title
  - [ ] Form labels and placeholders
  - [ ] Button text

- [ ] `src/components/project/ProjectCard.vue`
  - [ ] Action button text
  - [ ] Labels and tooltips

- [ ] `src/components/project/WorkItemRow.vue`
  - [ ] Status labels
  - [ ] Action text

#### Dataset Components
- [ ] `src/components/dataset/DatasetSelector.vue`
  - [ ] Selector label
  - [ ] Placeholder text
  - [ ] Empty state message

- [ ] `src/components/dataset/DatasetUpload.vue`
  - [ ] Upload instructions
  - [ ] File type hints
  - [ ] Error messages

#### ML Components
- [ ] `src/components/ml/prepare/PrepareStep.vue`
  - [ ] Step instructions
  - [ ] Button labels
  - [ ] Validation messages

- [ ] `src/components/ml/prepare/ColumnSelector.vue`
  - [ ] Column selection labels
  - [ ] Instructions
  - [ ] Validation messages

- [ ] `src/components/ml/tuning/TuningStep.vue`
  - [ ] Model selection labels
  - [ ] Tuning options
  - [ ] Status messages
  - [ ] Button text

- [ ] `src/components/ml/prediction/PredictionStep.vue`
  - [ ] Upload instructions
  - [ ] Mode selection labels
  - [ ] Button text
  - [ ] Status messages

- [ ] `src/components/ml/prediction/PredictionResult.vue`
  - [ ] Result labels
  - [ ] Download button text
  - [ ] Status messages

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

## Notes

- Ensure all validation messages use i18n
- Replace console.log messages that users see
- Update success/error toast messages
- Check for hard-coded strings in computed properties
- Test language switching on all updated pages
- Run `npm run i18n:check` after updates to verify coverage
