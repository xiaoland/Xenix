# Components Directory

Vue 3 components organized by domain using `<script setup lang="ts">` and Composition API.

## Directory Structure

```text
components/
├── common/         # Shared UI components
├── dataset/        # Dataset management
├── ml/             # ML workflow (main domain)
│   ├── prepare/    # Step 1: Data preparation
│   ├── tuning/     # Step 2: Model tuning
│   └── prediction/ # Step 3: Prediction
└── obsrv/          # Observation/logging
```

## Component Categories

### common/

Reusable UI components shared across the application:

- **AutoForm.vue** - Dynamic form generation from JSON Schema
  - Props: `modelValue`, `schema`, `readonly`
  - Renders form controls based on schema type (string, number, array, etc.)

- **ArrayInput.vue** - Array value input with add/remove functionality
  - Props: `modelValue`, `itemType`, `placeholder`, `disabled`

- **Steps.vue** - Workflow step indicator (wraps Ant Design Steps)

- **PageHeader.vue** - Application header with navigation

- **LanguageSwitcher.vue** - i18n language toggle

### dataset/

Dataset selection and upload components:

- **DatasetSelector.vue** - Select from existing datasets
- **UploadDataset.vue** - Upload new dataset files

### ml/

Main ML workflow components organized by step:

#### ml/prepare/

- **PrepareStep.vue** - Main container for data preparation
- **ColumnSelector.vue** - Select feature and target columns

#### ml/tuning/

Model tuning step (most complex):

- **TuningStep.vue** - Main tuning workflow container
- **ModelTuningTable.vue** - Table showing all models and their tuning status
- **ModelTuningRow.vue** - Individual model row in table
- **ModelTuningSubRow.vue** - Task details row (metrics, params, logs)
- **ModelAutoMetrics.vue** - Display tuning metrics (MSE, MAE, R²)
- **AutoTuneDialog.vue** - Start auto-tuning dialog
- **ManualTuneDialog.vue** - Manual parameter configuration dialog
- **ModelParamForm.vue** - Single parameter form
- **ModelParamGridForm.vue** - Parameter grid for GridSearchCV

#### ml/prediction/

- **PredictionStep.vue** - Upload prediction file and execute prediction

#### ml/ (root)

- **ModelSelector.vue** - Multi-select for choosing models to tune

### obsrv/

Observation and logging components:

- **LogPanel.vue** - Display task execution logs
- **TaskLogViewer.vue** - Task-specific log viewer

## Component Patterns

### Props/Emits

```typescript
const props = defineProps<{
  workItemId: number;
  selectedTaskId?: number | null;
}>();

const emit = defineEmits<{
  "update:selectedTaskId": [taskId: number | null];
  continue: [data: { model: string; taskId: number }];
  back: [];
}>();
```

### v-model Pattern

```typescript
const modelValue = defineModel<number | null>("selectedTaskId", {
  default: null,
});
```

## Styling

- Use UnoCSS utility classes for simple styles
- Use `<style scoped>` for component-specific styles
- Icons via UnoCSS: `<span class="i-mdi-plus" />`
