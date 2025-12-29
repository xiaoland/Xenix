# Model Tuning Components Refactoring

## Overview

This document describes the refactored architecture of the ModelTuningTable and ModelTuningRow components.

## Problem Statement

The original architecture had ModelTuningTable managing all data fetching, state management, and dialogs for all models. This created tight coupling and made the code difficult to maintain.

**Goal**: Make ModelTuningRow manage all tuning tasks (both auto-tune and manual-tune) of a single model.

## New Architecture

### ModelTuningRow (Self-Contained Model Manager)

Each `ModelTuningRow` instance is responsible for managing **one model** completely:

#### Responsibilities:
- Fetches training history for its model
- Fetches model metadata (for parameter schemas)
- Manages all dialogs:
  - ParamGrid dialog (for auto-tune configuration)
  - ManualTrain dialog (for manual parameter input)
  - Log viewer modal
- Manages task logs
- Renders parent row (model name + action buttons)
- Renders child rows (training history when expanded)
- Handles all user interactions for the model

#### Props:
```typescript
{
  modelName: string;        // Model identifier (e.g., "LinearRegression")
  modelLabel: string;       // Human-readable name
  workItemId: number;       // To fetch training history
  selectedTaskId: number | null;  // v-model for task selection
  isTuning: boolean;        // Disable buttons during tuning
  isExpanded: boolean;      // Show/hide training history
}
```

#### Events:
```typescript
{
  "update:selectedTaskId": (taskId: number | null) => void;
  "start-tune": (model, paramGrid?, trainingType?, parentTaskId?) => void;
  "toggle-expand": (modelName: string) => void;
}
```

#### Key Features:
- Uses `teleport` to render dialogs outside table structure (avoiding HTML issues)
- Fetches data lazily (only when expanded)
- Self-contained state management

### ModelTuningTable (Lightweight Container)

The table is now a simple coordinator:

#### Responsibilities:
- Fetches available models from work item
- Renders table structure (thead with columns)
- Iterates over models, rendering one ModelTuningRow per model
- Manages expand/collapse state
- Passes events up to parent (TuningStep)
- Determines global tuning state (for button disabling)

#### What it NO LONGER does:
- ❌ Fetch training history (moved to ModelTuningRow)
- ❌ Manage dialogs (moved to ModelTuningRow)
- ❌ Fetch task logs (moved to ModelTuningRow)
- ❌ Build complex table data structures (ModelTuningRow renders directly)

## Benefits

1. **Separation of Concerns**: Each model's logic is isolated
2. **Maintainability**: Changes to model-specific features only affect ModelTuningRow
3. **Testability**: ModelTuningRow can be tested independently
4. **Scalability**: Easy to add model-specific features
5. **Code Reduction**: 72 lines removed overall

## Component Flow

```
TuningStep
  └─ ModelTuningTable
      ├─ ModelTuningRow (model: "LinearRegression")
      │   ├─ Training History
      │   ├─ ParamGrid Dialog
      │   ├─ ManualTrain Dialog
      │   └─ Log Modal
      ├─ ModelTuningRow (model: "RandomForest")
      │   ├─ Training History
      │   ├─ ParamGrid Dialog
      │   ├─ ManualTrain Dialog
      │   └─ Log Modal
      └─ ...
```

## Data Flow

1. **ModelTuningTable** fetches available models from work item
2. For each model, it renders a **ModelTuningRow**
3. When expanded, **ModelTuningRow** fetches its training history
4. When user clicks "Auto Tune" or "Manual Train", **ModelTuningRow** shows its dialog
5. When user saves, **ModelTuningRow** emits "start-tune" event
6. Event bubbles up: ModelTuningRow → ModelTuningTable → TuningStep → Page

## Usage Example

```vue
<ModelTuningTable
  :work-item-id="workItemId"
  v-model:selected-task-id="selectedTaskId"
  @start-tune="handleStartTune"
/>
```

## Migration Notes

If you're updating code that uses these components:

1. **No changes needed** to components using ModelTuningTable (props/events unchanged)
2. **Don't pass** training history, logs, or dialog props to ModelTuningTable anymore
3. **ModelTuningRow** now manages its own data fetching

## Testing Considerations

- Test ModelTuningRow in isolation with mock model data
- Test ModelTuningTable with mock available models
- Test event propagation from row to table to parent

## Performance

- Training history is fetched **lazily** (only when row is expanded)
- Model metadata is fetched **once per model** on mount
- Dialog state is **isolated** per model (no global state pollution)
