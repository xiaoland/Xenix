# ML Backend Cleanup - Legacy Code Removal

## Summary

Ruthlessly removed all `auto-tune` and `manual-tune` naming. Standardized on:
- **batch-train** - GridSearchCV parameter optimization
- **single-train** - Training with specific parameters
- **predict** - Making predictions

## Changes Made

### Python Scripts
```
auto_tune_model.py    → batch_train_model.py
manual_tune_model.py  → single_train_model.py
```

### FC Workers
```
fc-workers/auto-tune/    → fc-workers/batch-train/
fc-workers/manual-tune/  → fc-workers/single-train/
```

### FC Adapters
```
src/adapters/aliyun-fc/auto-tune.ts    → batch-train.ts
src/adapters/aliyun-fc/manual-tune.ts  → single-train.ts
```

### FC Function Names
```
ml-auto-tune-worker    → ml-batch-train-worker
ml-manual-tune-worker  → ml-single-train-worker
```

### TypeScript Types (Backend)
```
AutoTuneOptions    → BatchTrainOptions
ManualTuneOptions  → SingleTrainOptions
AutoTuneRequest    → BatchTrainRequest
ManualTuneRequest  → SingleTrainRequest
```

### Functions
```
autoTune()    → batchTrain()
manualTune()  → singleTrain()
```

### Adapter Methods
```
adapter.autoTune()    → adapter.batchTrain()
adapter.manualTune()  → adapter.singleTrain()
```

## Files Deleted

### Backend (old duplicates)
- `packages/backend/src/business/ml/*.py` - All Python files (22 files)
- `packages/backend/src/business/ml/regression/` - All regression models (13 files)
- `packages/backend/python-workers/` - Entire directory (3 workers × 26 files each = 78 files)

### ML-Backend (renamed)
- Old FC worker directories deleted, recreated with new names
- Old adapter files deleted, recreated with new names

## Configuration Updates

### packages/ml-backend/s.yaml
```yaml
resources:
  ml-batch-train-worker:    # was ml-auto-tune-worker
  ml-single-train-worker:   # was ml-manual-tune-worker
  ml-predict-worker:        # unchanged
```

### packages/ml-backend/tsup.config.ts
```typescript
entry: [
  'src/adapters/aliyun-fc/batch-train.ts',   // was auto-tune.ts
  'src/adapters/aliyun-fc/single-train.ts',  // was manual-tune.ts
  'src/adapters/aliyun-fc/predict.ts',
]
```

### packages/ml-backend/scripts/copy-to-workers.js
```javascript
const workers = [
  { name: 'batch-train', handler: 'batch-train.js' },   // was auto-tune
  { name: 'single-train', handler: 'single-train.js' }, // was manual-tune
  { name: 'predict', handler: 'predict.js' },
];
```

## No Backward Compatibility

Following the principle "delete ruthlessly", no backward compatibility was maintained:
- No deprecated aliases
- No legacy function names
- No old type exports
- Clean break from old naming

## Three Operations

ML backend now has exactly three operations:

1. **batch-train** - Optimize hyperparameters with GridSearchCV
2. **single-train** - Train with specific parameter values
3. **predict** - Make predictions with trained model

## Comprehensive Cleanup - Phase 2

Extended cleanup to shared and backend packages:

### Shared Package
**Schemas (packages/shared/src/schemas/task.ts)**:
- AutoTuneTaskParameterSchema → BatchTrainTaskParameterSchema
- ManualTuneTaskParameterSchema → SingleTrainTaskParameterSchema
- AutoTuneTaskResultSchema → BatchTrainTaskResultSchema
- ManualTuneTaskResultSchema → SingleTrainTaskResultSchema
- AutoTuneTaskSchema → BatchTrainTaskSchema (with type: "batch-train")
- ManualTuneTaskSchema → SingleTrainTaskSchema (with type: "single-train")
- CreateAutoTuneTaskSchema → CreateBatchTrainTaskSchema
- CreateManualTuneTaskSchema → CreateSingleTrainTaskSchema
- All corresponding type exports updated

**Types (packages/shared/src/types/task.ts)**:
- AutoTuneTaskParameter → BatchTrainTaskParameter
- ManualTuneTaskParameter → SingleTrainTaskParameter
- AutoTuneTaskResult → BatchTrainTaskResult
- ManualTuneTaskResult → SingleTrainTaskResult
- AutoTuneTask → BatchTrainTask (with type: "batch-train")
- ManualTuneTask → SingleTrainTask (with type: "single-train")
- Updated Task union type and TaskInfo interface

### Backend Package
**Routes (packages/backend/src/routes/tune.ts)**:
- Endpoint: /auto-tune → /batch-train
- Endpoint: /manual-tune → /single-train
- Import: CreateAutoTuneTaskSchema → CreateBatchTrainTaskSchema
- Import: CreateManualTuneTaskSchema → CreateSingleTrainTaskSchema
- Task type: "auto-tune" → "batch-train"
- Task type: "manual-tune" → "single-train"
- FC function: ml-auto-tune-worker → ml-batch-train-worker
- FC function: ml-manual-tune-worker → ml-single-train-worker
- Response messages updated

**Job Processor (packages/backend/src/jobs/mlTaskProcessor.ts)**:
- Import: autoTune, manualTune → batchTrain, singleTrain
- MLTaskData type: "auto-tune" | "manual-tune" → "batch-train" | "single-train"
- Switch cases updated to use new function names

**Database Schema (packages/backend/src/database/schema.ts)**:
- Comment updated: 'auto-tune', 'train', 'predict' → 'batch-train', 'single-train', 'predict'

**ML Backend Adapter (packages/backend/src/adapters/ml-backend/aliyun-fc-adapter.ts)**:
- Log message: "Auto-tune task invoked via FC" → "Batch-train task invoked via FC"
- Log message: "Manual-tune task invoked via FC" → "Single-train task invoked via FC"

### Files Deleted (108 files total)
- packages/backend/python-workers/ - Entire directory (78 files)
- packages/backend/src/business/ml/*.py - 10 Python scripts
- packages/backend/src/business/ml/regression/ - 13 regression model files

## Commits

- `8b211fd` - refactor: remove auto-tune/manual-tune naming, use batch-train/single-train
- `0cb82fe` - refactor: complete auto-tune/manual-tune to batch-train/single-train cleanup

## Result

Clean, consistent codebase with no legacy naming confusion.
