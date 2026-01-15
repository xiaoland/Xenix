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
- `packages/backend/src/business/ml/*.py` - All Python files
- `packages/backend/src/business/ml/regression/` - All regression models
- `packages/backend/python-workers/` - Entire directory

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

## Commits

- `8b211fd` - refactor: remove auto-tune/manual-tune naming, use batch-train/single-train

## Result

Clean, consistent codebase with no legacy naming confusion.
