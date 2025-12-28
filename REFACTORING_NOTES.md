# Tuning Step Refactoring - Technical Documentation

## Overview
This refactoring addresses the issues in the tuning workflow by separating concerns between auto-tuning (hyperparameter grid search) and manual training (specific parameters), while fixing the boolean type serialization bug and improving code reusability.

## Problem Statements Addressed

### 1. ✅ ModelTuningTable Sub-rows Display
**Requirement**: Sub-rows should display tune type and parameters/ParamGrid

**Implementation**:
- Added "Tune Type & Parameters" column to ModelTuningTable
- Sub-rows now show:
  - Training type badge (Auto Tune / Train)
  - Parameter values formatted appropriately (arrays, objects, primitives)
- Added `formatParamValue()` helper function

### 2. ✅ Radio Button Selection
**Requirement**: Add radio to ModelTuningTable sub-rows for selecting tuning results

**Implementation**:
- Added "Select" column with radio buttons
- Only visible in sub-rows (history items)
- Emits `select-task` event with taskId and model
- Parent component tracks `selectedTaskId` state
- Selected task is used in prediction step

### 3. ✅ Separate Endpoints
**Requirement**: Remove upload.post.ts, implement tune.post.ts and train.post.ts

**Implementation**:

**tune.post.ts** (auto-tune):
- Parameters: `datasetId`, `features`, `target`, `model`, `paramGrid`
- Creates task with type: `"auto-tune"`
- Calls `tune()` function with optional paramGrid
- Uses GridSearchCV for hyperparameter optimization

**train.post.ts** (manual-train):
- Parameters: `datasetId`, `features`, `target`, `model`, `parameters`
- Creates task with type: `"train"`
- Calls `train()` function with specific parameters
- Trains single model with given parameters

**upload.post.ts**: REMOVED
- Old endpoint that mixed both concerns

### 4. ✅ Boolean Serialization Fix
**Requirement**: Fix boolean type input serialization (was getting string instead of bool)

**Implementation**:
- Created `AutoForm.vue` component
- Uses `<a-switch v-model:checked>` for boolean types
  - Correctly binds to boolean value
  - Serializes as `true`/`false` (not `"true"`/`"false"`)
- Both ParamGridDialog and ManualTrainDialog now use AutoForm

## Architecture

### Component Hierarchy
```
pages/index.vue
  └── TuningStep.vue
      └── ModelTuningTable.vue
          ├── ParamGridDialog.vue (uses AutoForm)
          └── ManualTrainDialog.vue (uses AutoForm)
```

### API Flow

**Auto-Tune Flow:**
```
User clicks "Auto Tune"
  → ParamGridDialog opens (AutoForm in paramGrid mode)
  → User configures parameter grids (arrays)
  → POST /api/tune
  → Creates "auto-tune" task
  → Calls ML.tune() → tune_model.py
  → GridSearchCV finds best parameters
  → Results saved with paramGrid
```

**Manual Train Flow:**
```
User clicks "Train"
  → ManualTrainDialog opens (AutoForm in parameters mode)
  → User sets specific parameters (single values, booleans as switches)
  → POST /api/train
  → Creates "train" task
  → Calls ML.train() → train_model.py
  → Model trained with specific parameters
  → Results saved with parameters
```

## AutoForm Component Design

### Modes
1. **paramGrid**: Array-based input for hyperparameter search
   - Each parameter accepts multiple values
   - Uses ArrayInput component
   - Example: `alpha: [0.1, 1.0, 10.0]`

2. **parameters**: Single-value input for direct training
   - Each parameter accepts one value
   - Uses appropriate input type:
     - Boolean → `<a-switch>`
     - Number/Integer → `<a-input-number>`
     - String → `<a-input>`
   - Example: `alpha: 1.0, fit_intercept: true`

### Type Handling
```typescript
getItemType(propSchema: any): string {
  if (propSchema.items) {
    return propSchema.items.type || "string";
  }
  if (Array.isArray(propSchema.default) && propSchema.default.length > 0) {
    const firstItem = propSchema.default[0];
    return typeof firstItem;
  }
  if (propSchema.type) {
    return propSchema.type;
  }
  return "string";
}
```

### Initialization Logic
```typescript
initializeFormData() {
  for (const [propName, propSchema] of Object.entries(schema.properties)) {
    if (props.modelValue && props.modelValue[propName] !== undefined) {
      // Use provided value
      data[propName] = props.modelValue[propName];
    } else if (schema.default !== undefined) {
      if (props.mode === "paramGrid") {
        // Arrays for paramGrid
        data[propName] = Array.isArray(schema.default) 
          ? [...schema.default] 
          : [schema.default];
      } else {
        // Single values for parameters
        data[propName] = Array.isArray(schema.default) 
          ? schema.default[0] 
          : schema.default;
      }
    } else {
      // Fallback defaults
      if (props.mode === "paramGrid") {
        data[propName] = [];
      } else {
        const itemType = getItemType(schema);
        data[propName] = itemType === "boolean" ? false 
          : itemType === "number" || itemType === "integer" ? 0 
          : "";
      }
    }
  }
}
```

## Database Schema

No changes to database schema. Uses existing task types:
- `"auto-tune"`: For hyperparameter grid search
- `"train"`: For manual training with specific parameters

Task parameter structure:
```json
{
  "model": "regression.ridge",
  "datasetId": "ds_123456",
  "featureColumns": ["feature1", "feature2"],
  "targetColumn": "target",
  "paramGrid": {           // For auto-tune
    "alpha": [0.1, 1.0, 10.0],
    "fit_intercept": [true, false]
  },
  "parameters": {          // For train
    "alpha": 1.0,
    "fit_intercept": true
  },
  "trainingType": "auto" | "manual"
}
```

## Python Scripts

### tune_model.py (existing, updated)
- Performs hyperparameter grid search
- Uses GridSearchCV
- Returns best parameters and metrics

### train_model.py (new)
- Trains model with specific parameters
- Uses `Model.create_model(parameters)`
- No grid search, direct training
- Returns parameters and metrics

Both scripts use:
- Same structured_output format
- Same base model interface
- Same evaluation metrics

## Testing Strategy

### Unit Testing Areas
1. AutoForm component
   - Test paramGrid mode with arrays
   - Test parameters mode with single values
   - Test boolean type handling
   - Test number/integer type handling

2. API endpoints
   - Test tune.post.ts with valid/invalid payloads
   - Test train.post.ts with valid/invalid payloads
   - Test dataset validation

3. Python scripts
   - Test train_model.py with various parameter types
   - Test model.create_model() integration

### Integration Testing
1. Complete auto-tune workflow
2. Complete manual train workflow
3. Task selection with radio buttons
4. Prediction with selected task

### Manual Testing Checklist
- [ ] Upload dataset
- [ ] Auto-tune a model
- [ ] Verify paramGrid dialog works
- [ ] Verify boolean arrays can be added
- [ ] Manual train a model
- [ ] Verify parameters dialog works
- [ ] Verify boolean switches work
- [ ] Check sub-row display
- [ ] Select a task via radio button
- [ ] Proceed to prediction
- [ ] Verify prediction uses selected task

## Migration Guide

### For Existing Code Using upload.post.ts

**Old:**
```typescript
const formData = new FormData();
formData.append("datasetId", datasetId);
formData.append("model", model);
formData.append("featureColumns", JSON.stringify(features));
formData.append("targetColumn", target);
formData.append("paramGrid", JSON.stringify(paramGrid));
formData.append("trainingType", "auto");

await $fetch("/api/upload", {
  method: "POST",
  body: formData,
});
```

**New (Auto-Tune):**
```typescript
await $fetch("/api/tune", {
  method: "POST",
  body: {
    datasetId,
    features,
    target,
    model,
    paramGrid, // optional
  },
});
```

**New (Manual Train):**
```typescript
await $fetch("/api/train", {
  method: "POST",
  body: {
    datasetId,
    features,
    target,
    model,
    parameters, // required
  },
});
```

## Performance Considerations

- AutoForm component uses `watch` with `deep: true` - acceptable for small forms
- Radio button selection is O(1) lookup
- Parameter formatting uses memoization where possible
- No performance degradation expected

## Security Considerations

- Both endpoints validate dataset existence
- Input validation for required fields
- Type checking at API level
- No new security vulnerabilities introduced

## Future Enhancements

1. Add validation rules to AutoForm based on JSON Schema
2. Support for nested parameter objects
3. Add parameter presets/templates
4. Comparison view for multiple tuning results
5. Export/import parameter configurations

## Backward Compatibility

- ✅ Existing training history preserved
- ✅ Existing task results readable
- ✅ Database schema unchanged
- ✅ Python model interface unchanged
- ⚠️ upload.post.ts removed (breaking change)

## Known Limitations

1. AutoForm doesn't support nested objects (not needed for current models)
2. ArrayInput for booleans requires text input ("true"/"false")
3. No parameter validation beyond type checking
4. Single task selection (no multi-select for comparison)

## Dependencies

No new dependencies added. Uses existing:
- Vue 3
- Ant Design Vue
- Nuxt 3
- TypeScript
- Python 3 with scikit-learn

## Conclusion

This refactoring successfully:
1. ✅ Separates auto-tuning and manual training concerns
2. ✅ Fixes boolean type serialization
3. ✅ Improves code reusability with AutoForm
4. ✅ Enhances UX with clear parameter display and selection
5. ✅ Maintains backward compatibility (except upload.post.ts)
6. ✅ Follows existing architecture patterns
