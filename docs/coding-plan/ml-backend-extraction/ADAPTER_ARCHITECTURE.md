# ML Backend Adapter Architecture

## Overview

The ML backend extraction now includes a proper adapter pairing architecture between `packages/backend` and `packages/ml-backend`.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    packages/backend                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           ML Backend Adapters                        │   │
│  │  (Choose HOW to invoke ml-backend)                   │   │
│  │                                                       │   │
│  │  ┌──────────────────┐      ┌──────────────────┐    │   │
│  │  │  SpawnAdapter    │      │ AliyunFCAdapter  │    │   │
│  │  │                  │      │                  │    │   │
│  │  │  • Spawns Node   │      │  • Uses FC SDK   │    │   │
│  │  │  • Local dev     │      │  • Production    │    │   │
│  │  │  • Full paths    │      │  • OSS keys      │    │   │
│  │  └────────┬─────────┘      └────────┬─────────┘    │   │
│  │           │                         │              │   │
│  └───────────┼─────────────────────────┼──────────────┘   │
│              │                         │                   │
└──────────────┼─────────────────────────┼───────────────────┘
               │                         │
               │ spawn node process      │ FC async invoke
               │ (stdio adapter)         │ (FC handlers)
               │                         │
┌──────────────▼─────────────────────────▼───────────────────┐
│                  packages/ml-backend                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐   │
│  │              ML Backend Adapters                    │   │
│  │  (Handle I/O based on environment)                  │   │
│  │                                                      │   │
│  │  ┌──────────────────┐      ┌──────────────────┐   │   │
│  │  │  stdio Adapter   │      │ Aliyun FC Handler│   │   │
│  │  │                  │      │                  │   │   │
│  │  │  • stdin/stdout  │      │  • FC event/ctx  │   │   │
│  │  │  • Full paths    │      │  • /mnt/oss paths│   │   │
│  │  │  • Local files   │      │  • Direct DB     │   │   │
│  │  └────────┬─────────┘      └────────┬─────────┘   │   │
│  │           │                         │             │   │
│  └───────────┼─────────────────────────┼─────────────┘   │
│              │                         │                  │
│  ┌───────────▼─────────────────────────▼─────────────┐   │
│  │              Core ML Functions                      │   │
│  │                                                      │   │
│  │    batchTrain()   singleTrain()   predict()        │   │
│  │                                                      │   │
│  │              Python ML Scripts                      │   │
│  │    auto_tune_model.py  manual_tune_model.py  ...   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Backend Adapters (packages/backend/src/adapters/ml-backend/)

### Interface
```typescript
interface MLBackendAdapter {
  autoTune(options: AutoTuneRequest): Promise<void>;
  manualTune(options: ManualTuneRequest): Promise<void>;
  predict(options: PredictRequest): Promise<void>;
  isAvailable(): boolean;
}
```

### 1. SpawnAdapter

**Purpose**: Local development execution

**How it works**:
- Spawns Node.js process: `node dist/adapters/stdio/index.js`
- Writes operation JSON to stdin
- Parses structured output from stdout
- Updates database with logs and results
- Handles task status transitions

**I/O Characteristics**:
- Input: Full local file paths (e.g., `/home/user/uploads/dataset.xlsx`)
- Output: Results captured from stdout and saved to database by backend
- Logs: Parsed from stdout and stored in database by backend

**When used**: Always available, used when FC is not configured

### 2. AliyunFCAdapter

**Purpose**: Production serverless execution

**How it works**:
- Uses `@alicloud/fc2` SDK to invoke FC functions asynchronously
- Passes OSS object keys (not full paths)
- FC functions have OSS bucket mounted at `/mnt/oss`
- ML backend reads from `/mnt/oss/<key>`
- Results and logs are written directly to database by ml-backend

**I/O Characteristics**:
- Input: OSS object keys (e.g., `datasets/123/data.xlsx`)
- FC reads from: `/mnt/oss/datasets/123/data.xlsx`
- Output: Results written directly to database by ml-backend
- Logs: Written directly to database by ml-backend

**When used**: When FC client is configured (production)

### Factory Function

```typescript
function getMLBackendAdapter(): MLBackendAdapter {
  // Try FC adapter first
  const fcAdapter = new AliyunFCAdapter();
  if (fcAdapter.isAvailable()) {
    return fcAdapter;
  }

  // Fallback to spawn adapter
  return new SpawnAdapter();
}
```

## ML Backend Adapters (packages/ml-backend/src/adapters/)

### 1. stdio Adapter

**Purpose**: Entry point for local spawned processes

**How it works**:
- Reads JSON operation from stdin
- Calls appropriate core function (batchTrain, singleTrain, predict)
- Creates DatabaseLogger if DATABASE_URL provided
- Writes structured JSON output to stdout
- Exits with code 0 (success) or 1 (failure)

**I/O Characteristics**:
- Input: stdin JSON with full local paths
- Output: stdout JSON (structured logs + result)
- Database: Optional - if DATABASE_URL provided, writes directly

**Example invocation**:
```bash
echo '{"operation":"batch-train","taskId":123,...}' | node dist/adapters/stdio/index.js
```

### 2. Aliyun FC Adapters

**Purpose**: Entry point for FC function invocations

**How it works**:
- FC handler receives event and context
- Extracts payload from event
- Calls appropriate core function
- Creates DatabaseLogger with DATABASE_URL from environment
- Returns FC response (statusCode, body)

**I/O Characteristics**:
- Input: FC event payload with OSS keys
- Reads from: `/mnt/oss/<key>` (OSS mounted via NAS)
- Output: Results written directly to database
- Logs: Written directly to database
- Returns: FC response for status tracking

**Three handlers**:
- `auto-tune.ts` → ml-auto-tune-worker
- `manual-tune.ts` → ml-manual-tune-worker
- `predict.ts` → ml-predict-worker

## Usage Example

### Route Handler (packages/backend/src/routes/tune.ts)

**Before (Manual FC checking)**:
```typescript
if (fcInvokeService.isAvailable()) {
  // Production path
  await fcInvokeService.invokeAsync({
    functionName: 'ml-auto-tune-worker',
    payload: {...}
  });
} else {
  // Local path
  setImmediate(() => {
    autoTune({...}).catch((error) => {...});
  });
}
```

**After (Adapter pattern)**:
```typescript
// Adapter automatically chooses FC or spawn
const inputFile = storage.getType() === 'oss'
  ? storage.getFilesystemPath(`datasets/${datasetId}/${dataset.fileName}`) // OSS key
  : dataset.filePath; // Full local path

setImmediate(() => {
  autoTune({
    inputFile,
    model,
    featureColumns,
    targetColumn,
    taskId,
    paramGrid,
  }).catch((error) => {
    logger.error({ error, taskId }, `Failed to execute auto-tune task`);
  });
});
```

### ML Function (packages/backend/src/business/ml/index.ts)

```typescript
export async function autoTune(options: AutoTuneOptions): Promise<void> {
  const adapter = getMLBackendAdapter(); // Gets FC or Spawn adapter

  await adapter.autoTune({
    taskId: options.taskId,
    inputFile: options.inputFile, // Path or OSS key depending on storage
    model: options.model,
    featureColumns: options.featureColumns,
    targetColumn: options.targetColumn,
    paramGrid: options.paramGrid,
  });
}
```

## Key Differences: Local vs Production

### Local Development (SpawnAdapter + stdio)

| Aspect | Local |
|--------|-------|
| Invocation | `spawn('node', ['dist/adapters/stdio/index.js'])` |
| Input paths | Full local paths (`/home/user/uploads/data.xlsx`) |
| Output | stdout → parsed by backend → saved to DB |
| Logs | stdout → parsed by backend → saved to DB |
| Process | Backend spawns child process |
| Blocking | Non-blocking (setImmediate) |

### Production (AliyunFCAdapter + FC handlers)

| Aspect | Production |
|--------|-----------|
| Invocation | FC SDK async invoke |
| Input paths | OSS keys (`datasets/123/data.xlsx`) |
| Mount | FC reads from `/mnt/oss/datasets/123/data.xlsx` |
| Output | ml-backend writes directly to DB |
| Logs | ml-backend writes directly to DB |
| Process | FC function (serverless) |
| Blocking | Non-blocking (async invoke) |

## Benefits

1. **Clean Abstraction**: Routes don't need to know about FC vs local execution
2. **Single Responsibility**: Each adapter handles one invocation method
3. **Easy Testing**: Can test adapters independently
4. **Flexible Deployment**: Easy to add new adapters (HTTP, message queue, etc.)
5. **Consistent Interface**: Same function signatures regardless of environment
6. **I/O Transparency**: Adapters handle path translation (OSS keys vs local paths)

## TODO: Route Updates

The routes still need to be updated to remove manual FC checking:

1. ✅ Created adapter interface and implementations
2. ✅ Updated `src/business/ml/index.ts` to use adapters
3. ⏳ Update `src/routes/tune.ts` to remove `if (fcInvokeService.isAvailable())`
4. ⏳ Update `src/routes/predict.ts` to remove `if (fcInvokeService.isAvailable())`
5. ⏳ Test both local and FC execution paths

## Future Enhancements

### HTTP Adapter
- Direct HTTP API for ml-backend
- RESTful endpoints
- Synchronous or asynchronous

### Message Queue Adapter
- BullMQ, RabbitMQ, or similar
- Async job processing
- Retry mechanism
- Priority queuing

### gRPC Adapter
- High-performance communication
- Streaming support
- Strong typing
