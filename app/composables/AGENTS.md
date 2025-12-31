# Composables Directory

Vue 3 Composition API functions for shared logic and state management.

## Overview

Composables encapsulate reusable logic that can be shared across components. Each composable returns reactive state and/or functions.

## Composables List

### Workflow Step Composables

#### usePrepareStep.ts

Data preparation step logic.

- Column selection management
- Dataset validation

#### usePredictionStep.ts

Prediction workflow logic.

```typescript
const {
  predictionFileList,    // File list for prediction
  isPredicting,          // Loading state
  predictionTask,        // Current prediction task
  beforeUpload,          // File validation
  startPrediction,       // Execute prediction
  downloadResults,       // Download prediction results
  resetPredictionStep,   // Reset state
} = usePredictionStep();
```

#### useUploadStep.ts

File upload step logic for training data.

### Task Management

#### useTaskPolling.ts

Background task status polling.

```typescript
const {
  pollTaskStatus,   // Poll until task completes
  pollTaskLogs,     // Poll task logs
  registerTask,     // Register new task
  clearTasks,       // Clear all registered tasks
} = useTaskPolling();
```

Key features:

- Automatic polling with configurable interval
- Status tracking (pending, running, completed, failed)
- Log aggregation

#### useModelTraining.ts

Model training execution.

```typescript
const { executeTrain } = useModelTraining();

// Execute auto or manual training
await executeTrain({
  datasetId,
  featureColumns,
  targetColumn,
  model,
  paramGrid,      // Optional for manual tuning
  workItemId,
}, "auto" | "manual");
```

#### useTrainingHistory.ts

Training history management and retrieval.

### Data Management

#### useDatasetRegistration.ts

Dataset registration and ID management.

```typescript
const {
  uploadedDatasetId,      // Current dataset ID
  registerFileAsDataset,  // Register uploaded file
  clearDatasetId,         // Clear registration
} = useDatasetRegistration();
```

#### useTableData.ts

Generic table data management with pagination.

#### useFileUpload.ts

File upload utilities.

- File validation
- Upload progress tracking
- Error handling

### UI Utilities

#### useFormatters.ts

Data formatting utilities.

```typescript
const {
  formatModelName,    // Format model name for display
  formatMetric,       // Format numeric metrics
  getStatusColor,     // Get color for task status
} = useFormatters();
```

#### useDialogManagement.ts

Dialog/modal state management.

```typescript
const {
  dialogVisible,
  openDialog,
  closeDialog,
} = useDialogManagement();
```

## Usage Patterns

### Basic Usage

```typescript
import { usePredictionStep } from "~/composables/usePredictionStep";

const {
  predictionFileList,
  isPredicting,
  startPrediction,
} = usePredictionStep();
```

### Shared State

Some composables maintain global state (singleton pattern):

```typescript
// useDatasetRegistration maintains a single uploadedDatasetId
// that persists across component instances
```

### Reactive Returns

All composables return reactive refs or computed properties:

```typescript
// These are reactive
const { isPredicting } = usePredictionStep();

// Can be used directly in templates
// <a-spin v-if="isPredicting" />
```

## Best Practices

1. **Single Responsibility** - Each composable handles one concern
2. **Return Cleanup** - Return reset functions for state cleanup
3. **Type Safety** - Use TypeScript for all parameters and returns
4. **Naming** - Prefix with `use` (e.g., `useTaskPolling`)
