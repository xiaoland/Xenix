# Prediction Refactoring Plan

## Overview

Split prediction functionality into two modes:

1. **File-based prediction** - Upload Excel file for batch predictions (existing)
2. **Inline prediction** - Input JSON array of data points, get JSON predictions back (new)

## Architecture Changes

### 1. Python Scripts (server/business/ml/)

#### 1.1 Create `predict_on_file.py`

- **Purpose**: File-based batch prediction (existing functionality)
- **Input (stdin JSON)**:

  ```json
  {
    "trainingDataPath": "/path/to/training.xlsx",  
    "predictionDataPath": "/path/to/prediction.xlsx",
    "outputPath": "/path/to/output.xlsx",
    "model": "ridge",
    "params": {"model__alpha": 1.0},
    "featureColumns": ["col1", "col2"],
    "targetColumn": "target"
  }
  ```

- **Output (stdout JSON)**: Structured logs + result with outputPath and numPredictions
- **Process**: Load files → Train model → Predict → Save Excel file

#### 1.2 Create `predict_on_json.py`

- **Purpose**: Inline JSON-based prediction (new)
- **Input (stdin JSON)**:

  ```json
  {
    "trainingDataPath": "/path/to/training.xlsx",
    "predictionData": [
      {"col1": 1.2, "col2": 3.4},
      {"col1": 5.6, "col2": 7.8}
    ],
    "model": "ridge",
    "params": {"model__alpha": 1.0},
    "featureColumns": ["col1", "col2"],
    "targetColumn": "target"
  }
  ```

- **Output (stdout JSON)**:

  ```json
  {
    "type": "result",
    "data": {
      "predictions": [10.5, 12.3],
      "model": "ridge",
      "numPredictions": 2
    }
  }
  ```

- **Process**: Load training file → Train model → Convert JSON to DataFrame → Predict → Return JSON

#### 1.3 Refactor `predict.py`

- Extract shared logic into helper functions:
  - `load_and_train_model(training_data_path, model_name, params, feature_columns, target_column, logger)`
  - `predict_on_dataframe(model, model_class, X_pred)`
- Both new scripts will reuse these helpers

---

### 2. Backend TypeScript (server/business/ml/index.ts)

#### 2.1 Create `predictFile` function

```typescript
export interface PredictFileOptions {
  trainingDataPath: string;
  predictionDataPath: string;
  outputPath: string;
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
}

export async function predictFile(options: PredictFileOptions): Promise<void> {
  await getInitPromise();
  const stdinData = { /* ... */ };
  await executePythonTask({
    script: getScriptPath("predict_on_file.py"),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}
```

#### 2.2 Create `predictInline` function

```typescript
export interface PredictInlineOptions {
  trainingDataPath: string;
  predictionData: Record<string, any>[]; // JSON array of input data
  model: string;
  params: Record<string, any>;
  featureColumns: string[];
  targetColumn: string;
  taskId: number;
}

export async function predictInline(options: PredictInlineOptions): Promise<void> {
  await getInitPromise();
  const stdinData = { /* ... */ };
  await executePythonTask({
    script: getScriptPath("predict_on_json.py"),
    stdinData,
    taskId,
    cwd: getWorkingDirectory(),
  });
}
```

#### 2.3 Deprecate `predict`

- do not keep backward compatibility, migrate all usage sites

---

### 3. API Endpoints (server/api/)

#### 3.1 Create `server/api/predict/by-file.post.ts`

- **Purpose**: File-based prediction (existing predict.post.ts logic)
- **Request**: FormData with:
  - `file`: Excel file OR `datasetId`: existing dataset ID
  - `model`: model name
  - `tuningTaskId`: trained model task ID
  - `workItemId`: work item ID
- **Response**: `{ success, taskId, outputFile }`
- **Process**:
  1. Validate file/datasetId
  2. Load tuning results from task
  3. Create prediction task
  4. Call `predictFile()` in background

#### 3.2 Create `server/api/predict/inline.post.ts`

- **Purpose**: JSON-based inline prediction (new)
- **Request**: JSON body:

  ```json
  {
    "predictionData": [{"col1": 1.2, "col2": 3.4}],
    "model": "ridge",
    "tuningTaskId": 123,
    "workItemId": 456
  }
  ```

- **Response**: `{ success, taskId, predictions }`
- **Process**:
  1. Load work item for training dataset + columns
  2. Load tuning results from task
  3. Create prediction task
  4. Call `predictInline()` in background
  5. Return predictions from task.result

#### 3.3 Deprecate `server/api/predict.post.ts`

- Move existing logic to `by-file.post.ts`
- Add deprecation notice or keep as alias

---

### 4. Frontend Services (app/services/)

#### 4.1 Update `predictionService.ts`

```typescript
export class PredictionService {
  // Existing file-based method (keep or rename to startFile)
  static async start(params: {
    file: File;
    model: string;
    tuningTaskId: number;
    workItemId: number;
  }): Promise<{ success: boolean; taskId: number; outputFile?: string }> {
    const formData = new FormData();
    // ... existing logic
    return await $fetch("/api/predict/by-file", {
      method: "POST",
      body: formData,
    });
  }

  // New inline prediction method
  static async predictInline(params: {
    predictionData: Record<string, any>[];
    model: string;
    tuningTaskId: number;
    workItemId: number;
  }): Promise<{ success: boolean; taskId: number; predictions?: number[] }> {
    return await $fetch("/api/predict/inline", {
      method: "POST",
      body: params,
    });
  }
}
```

---

### 5. Frontend UI (app/components/ml/prediction/)

#### 5.1 Update `PredictionStep.vue`

- Add mode selector:
  - Radio buttons: "Upload File" vs "Manual Input"
  - State: `predictionMode: 'file' | 'inline'`

- **File Mode** (existing):
  - Upload dragger component
  - "Generate Predictions" button
  - Download results button

- **Inline Mode** (new):
  - Dynamic table with editable rows
  - Columns based on `featureColumns` from work item
  - "Add Row" / "Remove Row" buttons
  - "Predict" button
  - Results display as table (input + predicted value)

#### 5.2 Table Implementation

```vue
<template>
  <!-- Mode Selector -->
  <a-radio-group v-model:value="predictionMode">
    <a-radio-button value="file">{{ t('prediction.uploadFile') }}</a-radio-button>
    <a-radio-button value="inline">{{ t('prediction.manualInput') }}</a-radio-button>
  </a-radio-group>

  <!-- File Mode -->
  <div v-if="predictionMode === 'file'">
    <!-- existing upload dragger -->
  </div>

  <!-- Inline Mode -->
  <div v-else>
    <a-table
      :columns="inputColumns"
      :data-source="inputData"
      :pagination="false"
    >
      <template #bodyCell="{ column, record, index }">
        <a-input-number
          v-if="column.dataIndex !== 'action'"
          v-model:value="record[column.dataIndex]"
          :step="0.01"
        />
        <a-button v-else @click="removeRow(index)" danger size="small">
          <span class="i-mdi-delete" />
        </a-button>
      </template>
    </a-table>
    
    <a-button @click="addRow" class="mt-2">
      <span class="i-mdi-plus" /> Add Row
    </a-button>
    
    <a-button @click="predictInline" type="primary" class="mt-4">
      Predict
    </a-button>

    <!-- Results Table -->
    <a-table v-if="inlinePredictions.length > 0" :columns="resultColumns" :data-source="inlinePredictions" />
  </div>
</template>
```

#### 5.3 State Management

```typescript
const predictionMode = ref<'file' | 'inline'>('file');
const inputData = ref<Record<string, any>[]>([]);
const inlinePredictions = ref<any[]>([]);

const inputColumns = computed(() => {
  // Generate columns from props.featureColumns + action column
});

const addRow = () => {
  const newRow = {};
  props.featureColumns.forEach(col => newRow[col] = 0);
  inputData.value.push(newRow);
};

const removeRow = (index: number) => {
  inputData.value.splice(index, 1);
};

const predictInline = async () => {
  const response = await PredictionService.predictInline({
    predictionData: inputData.value,
    model: props.model,
    tuningTaskId: props.taskId,
    workItemId: props.workItemId,
  });
  
  // Poll task status
  const result = await pollTaskStatus(response.taskId);
  inlinePredictions.value = result.task.result.predictions.map((pred, idx) => ({
    ...inputData.value[idx],
    prediction: pred,
  }));
};
```

---

### 6. i18n Updates (i18n/locales/)

#### 6.1 Add to `en.json`

```json
{
  "prediction": {
    "uploadFile": "Upload File",
    "manualInput": "Manual Input",
    "addRow": "Add Row",
    "removeRow": "Remove",
    "inputData": "Input Data",
    "predictedValue": "Predicted Value",
    "inlinePrediction": "Inline Prediction",
    "generateInlinePredictions": "Generate Predictions",
    "noInputDataError": "Please add at least one row of input data"
  }
}
```

#### 6.2 Add to `zh-CN.json`

(Chinese translations)

---

## Implementation Steps

1. **Python Scripts**
   - Extract shared helpers from predict.py
   - Create predict_on_file.py (mostly copy existing logic)
   - Create predict_on_json.py (new inline logic)
   - Test both scripts independently

2. **Backend Functions**
   - Add predictFile() and predictInline() to index.ts
   - Test with existing predict() calls

3. **API Endpoints**
   - Create predict/by-file.post.ts (copy from predict.post.ts)
   - Create predict/inline.post.ts (new endpoint)
   - Update or deprecate predict.post.ts

4. **Frontend Service**
   - Update PredictionService with new methods
   - Test API calls

5. **Frontend UI**
   - Add mode selector to PredictionStep.vue
   - Implement inline input table
   - Add inline prediction logic
   - Test user interactions

6. **i18n**
   - Add translation keys
   - Verify all UI text is translatable

7. **Testing**
   - Test file-based prediction (regression test)
   - Test inline prediction with various inputs
   - Test error handling
   - Test UI interactions

---

## Key Design Decisions

### Why split scripts?

- Clear separation of concerns
- File operations vs JSON operations
- Easier to test and maintain
- Different input/output formats

### Why keep both modes in one component?

- User convenience (single workflow)
- Shared context (work item, model, parameters)
- Consistent UX

### Task architecture

- Both modes create tasks for consistency
- Enables logging, status polling, error handling
- Inline predictions stored in task.result.predictions

### Backward compatibility

- Existing API can be aliased to by-file
- Or keep predict.post.ts as wrapper
- No breaking changes for existing code

---

## Success Criteria

- [ ] File-based prediction works as before (no regression)
- [ ] Inline prediction works with JSON input/output
- [ ] UI allows switching between modes
- [ ] Input table is dynamic based on feature columns
- [ ] Predictions display correctly in results table
- [ ] Task logs work for both modes
- [ ] Error handling works for both modes
- [ ] All text is internationalized
- [ ] Code is clean and follows project patterns
