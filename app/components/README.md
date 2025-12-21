# Components Documentation

This directory contains reusable Vue components for the Xenix ML platform.

## Component Structure

### Page Components (Step-based)

#### `UploadStep.vue`
**Purpose**: Handles training data file upload (Step 1)

**Props**: None (uses `v-model` for file list)

**Events**:
- `continue`: Emitted when user clicks "Continue to Model Training"

**Features**:
- Drag & drop file upload
- Excel file validation (.xlsx, .xls)
- Single file limit

---

#### `TrainingStep.vue`
**Purpose**: Model training, tuning, and comparison (Step 2)

**Props**:
- `availableModels`: Array of model options
- `selectedModels`: Array of selected model values
- `tuningStatus`: Record of model training statuses
- `tuningTasks`: Record of task IDs per model
- `isTuning`: Boolean loading state
- `isComparing`: Boolean loading state
- `comparisonResults`: Comparison results object
- `comparisonTaskId`: ID of comparison task
- `taskLogs`: Record of logs per task
- `activeLogTab`: Currently active log tab

**Events**:
- `start-tuning`: Start hyperparameter tuning
- `start-comparison`: Start model comparison
- `back`: Navigate to previous step
- `continue`: Navigate to next step
- `model-toggle`: Model selection toggled
- `update:selectedModels`: Selected models updated
- `update:activeLogTab`: Active log tab updated

**Composed of**:
- `ModelSelector`
- `TaskLogViewer`
- `ComparisonResults`

---

#### `PredictionStep.vue`
**Purpose**: Batch prediction using best model (Step 3)

**Props**:
- `bestModel`: Name of the best performing model
- `isPredicting`: Boolean loading state
- `predictionTask`: Prediction task object

**Events**:
- `predict`: Start prediction
- `back`: Navigate to previous step
- `reset`: Reset entire workflow

**Features**:
- File upload for prediction data
- Best model display
- Prediction status tracking
- Task status alerts

---

### Utility Components

#### `ModelSelector.vue`
**Purpose**: Grid of selectable ML models with status indicators

**Props**:
- `availableModels`: Array of `{label, value}` model options
- `tuningStatus`: Record of model statuses

**Events**:
- `toggle`: Model selection toggled (passes model value)

**Features**:
- Responsive grid layout (2-4 columns)
- Status tags (pending/running/completed/failed)
- Primary styling for selected models

---

#### `TaskLogViewer.vue`
**Purpose**: Tabbed interface for viewing task logs

**Props**:
- `tuningTasks`: Record of tuning task IDs
- `comparisonTaskId`: Comparison task ID
- `taskLogs`: Record of log arrays per task

**Features**:
- One tab per tuning task
- Additional tab for comparison task
- Active tab management via `v-model`

**Composed of**:
- `LogPanel` (for each tab)

---

#### `LogPanel.vue`
**Purpose**: Terminal-style log display

**Props**:
- `logs`: Array of log objects with `{id, timestamp, severity, message}`

**Features**:
- Color-coded severity levels:
  - DEBUG: Gray
  - INFO: White
  - WARNING: Yellow
  - ERROR: Red
  - CRITICAL: Dark Red
- Formatted timestamps
- Dark terminal theme
- Scrollable with max height

---

#### `ComparisonResults.vue`
**Purpose**: Table displaying model comparison metrics

**Props**:
- `comparisonResults`: Object with `{results, bestModel}`

**Features**:
- Ant Design table with borders
- Best model highlighted with ⭐ tag
- Metrics columns: MSE, MAE, R² (train & test)
- Non-paginated display

---

## Component Hierarchy

```
index.vue (Main Page)
├── UploadStep.vue
├── TrainingStep.vue
│   ├── ModelSelector.vue
│   ├── TaskLogViewer.vue
│   │   └── LogPanel.vue (multiple instances)
│   └── ComparisonResults.vue
└── PredictionStep.vue
```

## Benefits of Component Breakdown

1. **Maintainability**: Each component has a single responsibility
2. **Reusability**: Components can be used in other pages/contexts
3. **Testability**: Smaller components are easier to unit test
4. **Readability**: Main page is now ~340 lines vs original 623 lines
5. **Collaboration**: Multiple developers can work on different components
6. **Performance**: Better code splitting and lazy loading potential

## File Size Comparison

- **Original** `index.vue`: 623 lines
- **Refactored** `index.vue`: ~340 lines
- **Components**: 7 files, average ~80 lines each

**Total reduction**: Main page reduced by 45% in size
