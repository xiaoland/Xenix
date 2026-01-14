# Xenix Backend Aliyun FC Enhancement Implementation Plan

## Overview

This plan enhances the Xenix backend's Aliyun Function Compute deployment with:
1. **Storage abstraction layer** supporting both local filesystem and Aliyun OSS (mounted as filesystem in FC)
2. **Python layer automation** using serverless-devs for simplified deployment
3. **FC Async Task Integration** replacing BullMQ for serverless-native async processing
4. **Separate Python ML functions** invoked asynchronously by the backend
5. **Frontend direct OSS upload** with backend handling metadata only

## Current State Analysis

### What Works
- Backend refactored for FC with tsup bundling ([tsup.config.fc.ts](../../../packages/backend/tsup.config.fc.ts))
- Build scripts: `build:fc`, `package:fc` create deployment package
- BullMQ infrastructure exists but will be removed
- Python ML scripts in [src/business/ml/](../../../packages/backend/src/business/ml/)

### Changes from Original Architecture
1. **No Redis/BullMQ**: Use FC async task invocation instead
2. **OSS as mounted filesystem**: Worker accesses OSS files directly via mount point
3. **Frontend uploads to OSS**: Backend receives metadata only, not file bytes
4. **Separate Python functions**: Pure Python functions for ML tasks (no Node.js wrapper)

---

## Architecture Design

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Browser)                       │
│                                                                   │
│  1. Get presigned URL from backend                              │
│  2. Upload file directly to OSS                                 │
│  3. Send metadata to backend                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend HTTP Function                         │
│                      (Node.js/Hono)                             │
│                                                                   │
│  - Handle API requests                                          │
│  - Generate presigned OSS URLs                                  │
│  - Store dataset metadata in RDS                                │
│  - Invoke Python ML functions asynchronously                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ FC Async Invoke
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Python ML Worker Functions                     │
│                      (Pure Python)                              │
│                                                                   │
│  - auto-tune-worker                                             │
│  - manual-tune-worker                                           │
│  - predict-worker                                               │
│                                                                   │
│  OSS mounted at /mnt/oss → direct file access                  │
└─────────────────────────────────────────────────────────────────┘
```

### OSS Mount Configuration

In FC, OSS bucket is mounted to filesystem:
- **Mount point**: `/mnt/oss/`
- **Bucket**: `xenix-data`
- **Access**: Direct filesystem operations (no SDK needed in worker)
- **Path structure**:
  - Datasets: `/mnt/oss/datasets/{datasetId}/{filename}`
  - Results: `/mnt/oss/predictions/{taskId}/output.xlsx`

### Storage Key Patterns

- **Datasets**: `datasets/{datasetId}/{timestamp}_{filename}`
- **Predictions**: `predictions/{taskId}/output.xlsx`
- **Temporary**: `tmp/{uuid}/{filename}`

---

## Implementation Strategy

### Phase 1: Storage Abstraction Layer

**Goal**: Create interface supporting local filesystem (dev) and OSS (production).

#### 1.1 Core Storage Schema & Interface

Create [src/storage/schemas.ts](../../../packages/backend/src/storage/schemas.ts):

```typescript
import { z } from 'zod';

// OSS configuration schema
export const ossConfigSchema = z.object({
  region: z.string(),
  accessKeyId: z.string(),
  accessKeySecret: z.string(),
  bucket: z.string(),
  endpoint: z.string().optional(),
});

export type OSSConfig = z.infer<typeof ossConfigSchema>;

// Storage operation results
export const fileMetadataSchema = z.object({
  size: z.number(),
  mtime: z.date(),
  contentType: z.string().optional(),
});

export type FileMetadata = z.infer<typeof fileMetadataSchema>;

// Presigned URL request
export const presignedUrlRequestSchema = z.object({
  key: z.string(),
  expiresIn: z.number().default(3600), // 1 hour
  contentType: z.string().optional(),
});

export type PresignedUrlRequest = z.infer<typeof presignedUrlRequestSchema>;

// Presigned URL response
export const presignedUrlResponseSchema = z.object({
  url: z.string().url(),
  key: z.string(),
  expiresAt: z.date(),
});

export type PresignedUrlResponse = z.infer<typeof presignedUrlResponseSchema>;
```

Create [src/storage/StorageService.ts](../../../packages/backend/src/storage/StorageService.ts):

```typescript
import { FileMetadata, PresignedUrlRequest, PresignedUrlResponse } from './schemas';

export interface StorageService {
  // Generate presigned URL for frontend upload
  generatePresignedUploadUrl(request: PresignedUrlRequest): Promise<PresignedUrlResponse>;

  // Generate presigned URL for frontend download
  generatePresignedDownloadUrl(key: string, expiresIn?: number): Promise<string>;

  // Backend operations
  exists(key: string): Promise<boolean>;
  delete(key: string): Promise<void>;
  stat(key: string): Promise<FileMetadata>;

  // Get filesystem path (for mounted OSS or local path)
  getFilesystemPath(key: string): string;

  // Copy file within storage (for result files)
  copy(sourceKey: string, destKey: string): Promise<void>;
}
```

**Key Design Decision**:
- No `upload()` method - frontend uploads directly to OSS via presigned URL
- `getFilesystemPath()` returns mount point path in FC, local path in dev
- All file access uses filesystem operations, no OSS SDK in worker

#### 1.2 Local Implementation

Create [src/storage/LocalStorage.ts](../../../packages/backend/src/storage/LocalStorage.ts):

```typescript
import fs from 'fs/promises';
import path from 'path';
import { StorageService } from './StorageService';
import { FileMetadata, PresignedUrlRequest, PresignedUrlResponse } from './schemas';

export class LocalStorage implements StorageService {
  constructor(private basePath: string) {}

  async generatePresignedUploadUrl(
    request: PresignedUrlRequest
  ): Promise<PresignedUrlResponse> {
    // For local dev, return a fake "presigned URL" that points to backend
    // Frontend will actually POST to backend's upload endpoint
    const expiresAt = new Date(Date.now() + request.expiresIn * 1000);

    return {
      url: `http://localhost:3000/upload/local/${request.key}`,
      key: request.key,
      expiresAt,
    };
  }

  async generatePresignedDownloadUrl(key: string, expiresIn = 3600): Promise<string> {
    return `http://localhost:3000/download/${key}`;
  }

  async exists(key: string): Promise<boolean> {
    try {
      await fs.access(this.getFilesystemPath(key));
      return true;
    } catch {
      return false;
    }
  }

  async delete(key: string): Promise<void> {
    await fs.unlink(this.getFilesystemPath(key));
  }

  async stat(key: string): Promise<FileMetadata> {
    const stats = await fs.stat(this.getFilesystemPath(key));
    return {
      size: stats.size,
      mtime: stats.mtime,
    };
  }

  getFilesystemPath(key: string): string {
    return path.join(this.basePath, key);
  }

  async copy(sourceKey: string, destKey: string): Promise<void> {
    const sourcePath = this.getFilesystemPath(sourceKey);
    const destPath = this.getFilesystemPath(destKey);
    await fs.mkdir(path.dirname(destPath), { recursive: true });
    await fs.copyFile(sourcePath, destPath);
  }
}
```

#### 1.3 OSS Implementation

Create [src/storage/OSSStorage.ts](../../../packages/backend/src/storage/OSSStorage.ts):

```typescript
import OSS from 'ali-oss';
import path from 'path';
import fs from 'fs/promises';
import { StorageService } from './StorageService';
import { FileMetadata, PresignedUrlRequest, PresignedUrlResponse, OSSConfig } from './schemas';

export class OSSStorage implements StorageService {
  private client: OSS;
  private mountPoint: string;

  constructor(config: OSSConfig, mountPoint = '/mnt/oss') {
    this.client = new OSS({
      region: config.region,
      accessKeyId: config.accessKeyId,
      accessKeySecret: config.accessKeySecret,
      bucket: config.bucket,
      endpoint: config.endpoint,
    });
    this.mountPoint = mountPoint;
  }

  async generatePresignedUploadUrl(
    request: PresignedUrlRequest
  ): Promise<PresignedUrlResponse> {
    const url = await this.client.signatureUrl(request.key, {
      method: 'PUT',
      expires: request.expiresIn,
      'Content-Type': request.contentType,
    });

    const expiresAt = new Date(Date.now() + request.expiresIn * 1000);

    return {
      url,
      key: request.key,
      expiresAt,
    };
  }

  async generatePresignedDownloadUrl(key: string, expiresIn = 3600): Promise<string> {
    return await this.client.signatureUrl(key, {
      method: 'GET',
      expires: expiresIn,
    });
  }

  async exists(key: string): Promise<boolean> {
    try {
      await fs.access(this.getFilesystemPath(key));
      return true;
    } catch {
      return false;
    }
  }

  async delete(key: string): Promise<void> {
    // Delete from both OSS and mounted filesystem
    await this.client.delete(key);
  }

  async stat(key: string): Promise<FileMetadata> {
    // Use filesystem since OSS is mounted
    const stats = await fs.stat(this.getFilesystemPath(key));
    return {
      size: stats.size,
      mtime: stats.mtime,
    };
  }

  getFilesystemPath(key: string): string {
    // Return mount point path - OSS is accessible as filesystem
    return path.join(this.mountPoint, key);
  }

  async copy(sourceKey: string, destKey: string): Promise<void> {
    // Use OSS copy operation (more efficient than filesystem copy)
    await this.client.copy(destKey, sourceKey);
  }
}
```

**Dependencies**: Install `ali-oss` package:
```bash
cd packages/backend
pnpm add ali-oss
pnpm add -D @types/ali-oss
```

#### 1.4 Factory & Configuration

Update [src/config/index.ts](../../../packages/backend/src/config/index.ts):

```typescript
import { z } from 'zod';

const configSchema = z.object({
  // ... existing config

  // Storage configuration
  STORAGE_TYPE: z.enum(['local', 'oss']).default('local'),
  UPLOAD_DIR: z.string().default('./uploads'),

  // OSS configuration (required when STORAGE_TYPE=oss)
  OSS_REGION: z.string().optional(),
  OSS_ACCESS_KEY_ID: z.string().optional(),
  OSS_ACCESS_KEY_SECRET: z.string().optional(),
  OSS_BUCKET: z.string().optional(),
  OSS_ENDPOINT: z.string().optional(),
  OSS_MOUNT_POINT: z.string().default('/mnt/oss'),
});

export type Config = z.infer<typeof configSchema>;

// Validate at runtime
export const config = configSchema.parse(process.env);
```

Create [src/storage/index.ts](../../../packages/backend/src/storage/index.ts):

```typescript
import { StorageService } from './StorageService';
import { LocalStorage } from './LocalStorage';
import { OSSStorage } from './OSSStorage';
import { config } from '../config';
import { ossConfigSchema } from './schemas';

export function createStorageService(): StorageService {
  if (config.STORAGE_TYPE === 'oss') {
    const ossConfig = ossConfigSchema.parse({
      region: config.OSS_REGION,
      accessKeyId: config.OSS_ACCESS_KEY_ID,
      accessKeySecret: config.OSS_ACCESS_KEY_SECRET,
      bucket: config.OSS_BUCKET,
      endpoint: config.OSS_ENDPOINT,
    });

    return new OSSStorage(ossConfig, config.OSS_MOUNT_POINT);
  }

  return new LocalStorage(config.UPLOAD_DIR);
}

export const storage = createStorageService();
export * from './StorageService';
export * from './schemas';
```

#### 1.5 Migration of File Operations

**1. Dataset Upload Flow** - Update [src/routes/datasets.ts](../../../packages/backend/src/routes/datasets.ts):

```typescript
import { storage } from '../storage';
import { presignedUrlRequestSchema } from '../storage/schemas';

// New endpoint: Generate presigned URL for upload
app.post('/data/upload-url', async (c) => {
  const body = presignedUrlRequestSchema.parse(await c.req.json());

  const result = await storage.generatePresignedUploadUrl({
    key: `datasets/${body.datasetId}/${Date.now()}_${body.filename}`,
    expiresIn: 3600,
    contentType: body.contentType,
  });

  return c.json(result);
});

// Updated endpoint: Create dataset metadata (after frontend upload)
app.post('/data', async (c) => {
  const { name, description, projectId, storageKey, fileSize } = await c.req.json();

  // Verify file exists in storage
  const exists = await storage.exists(storageKey);
  if (!exists) {
    return c.json({ error: 'File not found in storage' }, 400);
  }

  // Analyze file structure
  const localPath = storage.getFilesystemPath(storageKey);
  const analysis = await analyzeExcelFile(localPath);

  // Create dataset record
  const dataset = await DatasetService.createDataset({
    name,
    description,
    projectId,
    storageKey,  // Store key, not full path
    fileName: path.basename(storageKey),
    fileSize,
    ...analysis,
  });

  return c.json(dataset, 201);
});
```

**2. Dataset Analysis** - Update [src/utils/datasetUtils.ts](../../../packages/backend/src/utils/datasetUtils.ts):

```typescript
import * as XLSX from 'xlsx';
import fs from 'fs/promises';

// Function signature updated to accept filesystem path
export async function analyzeExcelFile(filePath: string) {
  const fileBuffer = await fs.readFile(filePath);
  const workbook = XLSX.read(fileBuffer, { type: 'buffer' });

  // ... existing analysis logic

  return {
    columns,
    rowCount,
    // ... other metadata
  };
}
```

**3. Download Endpoint** - Update [src/routes/download.ts](../../../packages/backend/src/routes/download.ts):

```typescript
import { storage } from '../storage';

app.get('/download/:id', async (c) => {
  const taskId = Number(c.req.param('id'));

  const task = await taskRepository.findById(taskId);
  if (!task?.result?.outputFile) {
    return c.json({ error: 'Result not found' }, 404);
  }

  const storageKey = task.result.outputFile;

  // Generate presigned download URL
  const downloadUrl = await storage.generatePresignedDownloadUrl(storageKey);

  // Redirect to presigned URL
  return c.redirect(downloadUrl);
});
```

**4. Remove BullMQ** - Delete or archive:
- [src/jobs/mlTaskWorker.ts](../../../packages/backend/src/jobs/mlTaskWorker.ts)
- [src/jobs/mlTaskProcessor.ts](../../../packages/backend/src/jobs/mlTaskProcessor.ts)
- [src/queues/](../../../packages/backend/src/queues/)

---

### Phase 2: Python ML Worker Functions

**Goal**: Create pure Python FC functions for ML processing.

#### 2.1 Python Function Structure

Create [python-workers/](../../../packages/backend/python-workers/) directory:

```
python-workers/
├── auto_tune/
│   ├── index.py           # FC handler
│   ├── requirements.txt   # Python deps
│   └── ml/                # Copied from src/business/ml/
├── manual_tune/
│   ├── index.py
│   ├── requirements.txt
│   └── ml/
└── predict/
    ├── index.py
    ├── requirements.txt
    └── ml/
```

#### 2.2 Auto-Tune Worker

Create [python-workers/auto_tune/index.py](../../../packages/backend/python-workers/auto_tune/index.py):

```python
import json
import sys
import os
from ml.auto_tune_model import auto_tune

def handler(event, context):
    """
    FC handler for auto-tune tasks
    Event structure:
    {
      "taskId": 123,
      "inputFile": "/mnt/oss/datasets/1/data.xlsx",
      "model": "regression.linear_regression",
      "featureColumns": ["col1", "col2"],
      "targetColumn": "target",
      "paramGrid": {...}
    }
    """
    try:
        # Parse event
        if isinstance(event, str):
            event = json.loads(event)
        elif isinstance(event, bytes):
            event = json.loads(event.decode('utf-8'))

        # Validate required fields
        required = ['taskId', 'inputFile', 'model', 'featureColumns', 'targetColumn']
        for field in required:
            if field not in event:
                raise ValueError(f"Missing required field: {field}")

        # Run auto-tune
        result = auto_tune(
            input_file=event['inputFile'],
            model=event['model'],
            feature_columns=event['featureColumns'],
            target_column=event['targetColumn'],
            param_grid=event.get('paramGrid'),
            task_id=event['taskId']
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'taskId': event['taskId'],
                'status': 'completed',
                'result': result
            })
        }

    except Exception as e:
        print(f"Error in auto-tune: {str(e)}", file=sys.stderr)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'taskId': event.get('taskId'),
                'status': 'failed',
                'error': str(e)
            })
        }
```

Create [python-workers/auto_tune/requirements.txt](../../../packages/backend/python-workers/auto_tune/requirements.txt):

```txt
pandas>=2.3.3
numpy>=1.26.0
scikit-learn>=1.8.0
xgboost>=2.1.3
lightgbm>=4.6.0
statsmodels>=0.14.6
openpyxl>=3.1.5
pydantic>=2.12.5
psycopg2-binary>=2.9.10
```

#### 2.3 Copy ML Scripts

Create [scripts/copy-ml-to-workers.js](../../../packages/backend/scripts/copy-ml-to-workers.js):

```javascript
import fs from 'fs-extra';
import path from 'path';

const workers = ['auto_tune', 'manual_tune', 'predict'];
const mlSourceDir = path.join(process.cwd(), 'src', 'business', 'ml');

async function copyMLScripts() {
  for (const worker of workers) {
    const destDir = path.join(process.cwd(), 'python-workers', worker, 'ml');

    console.log(`Copying ML scripts to ${worker}...`);
    await fs.copy(mlSourceDir, destDir, {
      filter: (src) => {
        // Copy only .py files
        return !src.includes('.ts') && !src.includes('__pycache__');
      }
    });
  }

  console.log('✓ ML scripts copied to all workers');
}

copyMLScripts().catch(console.error);
```

#### 2.4 Backend Async Invocation

Create [src/services/FCInvokeService.ts](../../../packages/backend/src/services/FCInvokeService.ts):

```typescript
import { z } from 'zod';
import { config } from '../config';

// Aliyun FC SDK
import FCClient from '@alicloud/fc2';

const fcInvokeRequestSchema = z.object({
  functionName: z.string(),
  payload: z.record(z.any()),
  invocationType: z.enum(['Sync', 'Async']).default('Async'),
});

type FCInvokeRequest = z.infer<typeof fcInvokeRequestSchema>;

export class FCInvokeService {
  private client: FCClient;

  constructor() {
    this.client = new FCClient(config.OSS_REGION, {
      accessKeyID: config.OSS_ACCESS_KEY_ID!,
      accessKeySecret: config.OSS_ACCESS_KEY_SECRET!,
      endpoint: `https://${config.OSS_REGION}.fc.aliyuncs.com`,
    });
  }

  async invokeAsync(request: FCInvokeRequest): Promise<void> {
    const validated = fcInvokeRequestSchema.parse(request);

    await this.client.invokeFunction(
      'xenix', // service name
      validated.functionName,
      Buffer.from(JSON.stringify(validated.payload)),
      {
        'X-Fc-Invocation-Type': validated.invocationType,
      }
    );
  }
}

export const fcInvokeService = new FCInvokeService();
```

**Dependencies**:
```bash
pnpm add @alicloud/fc2
```

#### 2.5 Update Task Submission

Update [src/routes/tune.ts](../../../packages/backend/src/routes/tune.ts):

```typescript
import { storage } from '../storage';
import { fcInvokeService } from '../services/FCInvokeService';

// Line 101-112: Replace setImmediate with FC async invoke
const storageKey = `datasets/${datasetId}/${dataset.fileName}`;
const inputFile = storage.getFilesystemPath(storageKey);

// Invoke auto-tune worker asynchronously
await fcInvokeService.invokeAsync({
  functionName: 'auto-tune-worker',
  payload: {
    taskId,
    inputFile,  // Mount point path: /mnt/oss/datasets/...
    model,
    featureColumns,
    targetColumn,
    paramGrid,
  },
  invocationType: 'Async',
});

return c.json({ taskId, message: "Auto-tune started" }, 201);
```

Similar updates for:
- Manual tune (lines 205-216)
- Predict inline [src/routes/predict.ts](../../../packages/backend/src/routes/predict.ts) (lines 127-143)

---

### Phase 3: Python Layer & Deployment Automation

#### 3.1 Layer Build Script

Create [scripts/build-python-layer.js](../../../packages/backend/scripts/build-python-layer.js):

```javascript
import fs from 'fs-extra';
import path from 'path';
import { execSync } from 'child_process';

const layerDir = path.join(process.cwd(), 'python-layer');
const pythonDir = path.join(layerDir, 'python');
const sitePackagesDir = path.join(pythonDir, 'lib', 'python3.10', 'site-packages');

async function buildPythonLayer() {
  console.log('Building Python layer for Aliyun FC...');

  await fs.remove(layerDir);
  await fs.mkdirs(sitePackagesDir);

  console.log('Installing Python dependencies...');
  execSync(
    `pip install -r python-workers/auto_tune/requirements.txt -t ${sitePackagesDir} --no-cache-dir`,
    { stdio: 'inherit' }
  );

  console.log('\n✓ Python layer built successfully!');
  console.log(`  Location: ${layerDir}`);
  console.log('  Next: Run "pnpm run upload:layer"');
}

buildPythonLayer().catch(console.error);
```

#### 3.2 Serverless-Devs Configuration

Create [s.yaml](../../../packages/backend/s.yaml):

```yaml
edition: 3.0.0
name: xenix-backend-app
access: default

vars:
  region: cn-hangzhou
  ossMount:
    bucket: xenix-data
    mountPoint: /mnt/oss

resources:
  # Python Layer
  xenix-python-layer:
    component: fc3
    props:
      region: ${vars.region}
      layerName: xenix-python-deps
      code: ./python-layer
      description: Python ML dependencies
      compatibleRuntime:
        - python3.10

  # Backend HTTP Function
  xenix-backend:
    component: fc3
    props:
      region: ${vars.region}
      functionName: xenix-backend
      runtime: custom.debian10
      handler: index.handler
      memorySize: 2048
      timeout: 60
      code: ./fc-deploy.zip
      environmentVariables:
        NODE_ENV: production
        STORAGE_TYPE: oss
        OSS_MOUNT_POINT: ${vars.ossMount.mountPoint}
        # Add other vars from .env.fc.example
      nasConfig:
        userId: 10003
        groupId: 10003
        mountPoints:
          - serverAddr: ${vars.ossMount.bucket}.${vars.region}.oss-dls.aliyuncs.com:/${vars.ossMount.bucket}/
            nasDir: /mnt/oss
            fcDir: ${vars.ossMount.mountPoint}
      triggers:
        - triggerConfig:
            methods: [GET, POST, PUT, DELETE]
            authType: anonymous
          triggerName: httpTrigger
          triggerType: http

  # Auto-Tune Worker
  auto-tune-worker:
    component: fc3
    props:
      region: ${vars.region}
      functionName: auto-tune-worker
      runtime: python3.10
      handler: index.handler
      memorySize: 4096
      timeout: 600
      code: ./python-workers/auto_tune
      layers:
        - ${resources.xenix-python-layer.output.arn}
      environmentVariables:
        PYTHONPATH: /opt/python
      nasConfig:
        userId: 10003
        groupId: 10003
        mountPoints:
          - serverAddr: ${vars.ossMount.bucket}.${vars.region}.oss-dls.aliyuncs.com:/${vars.ossMount.bucket}/
            nasDir: /mnt/oss
            fcDir: ${vars.ossMount.mountPoint}

  # Manual-Tune Worker
  manual-tune-worker:
    component: fc3
    props:
      region: ${vars.region}
      functionName: manual-tune-worker
      runtime: python3.10
      handler: index.handler
      memorySize: 4096
      timeout: 600
      code: ./python-workers/manual_tune
      layers:
        - ${resources.xenix-python-layer.output.arn}
      environmentVariables:
        PYTHONPATH: /opt/python
      nasConfig:
        userId: 10003
        groupId: 10003
        mountPoints:
          - serverAddr: ${vars.ossMount.bucket}.${vars.region}.oss-dls.aliyuncs.com:/${vars.ossMount.bucket}/
            nasDir: /mnt/oss
            fcDir: ${vars.ossMount.mountPoint}

  # Predict Worker
  predict-worker:
    component: fc3
    props:
      region: ${vars.region}
      functionName: predict-worker
      runtime: python3.10
      handler: index.handler
      memorySize: 4096
      timeout: 600
      code: ./python-workers/predict
      layers:
        - ${resources.xenix-python-layer.output.arn}
      environmentVariables:
        PYTHONPATH: /opt/python
      nasConfig:
        userId: 10003
        groupId: 10003
        mountPoints:
          - serverAddr: ${vars.ossMount.bucket}.${vars.region}.oss-dls.aliyuncs.com:/${vars.ossMount.bucket}/
            nasDir: /mnt/oss
            fcDir: ${vars.ossMount.mountPoint}
```

#### 3.3 Update package.json Scripts

Update [package.json](../../../packages/backend/package.json):

```json
{
  "scripts": {
    "build:fc": "pnpm run build:shared && tsup --config tsup.config.fc.ts && pnpm run copy:assets",
    "copy:assets": "node scripts/copy-assets.js",
    "copy:ml-workers": "node scripts/copy-ml-to-workers.js",
    "package:fc": "pnpm run build:fc && node scripts/package-fc.js",

    "build:layer": "node scripts/build-python-layer.js",
    "build:workers": "pnpm run copy:ml-workers",

    "deploy:layer": "s deploy xenix-python-layer",
    "deploy:backend": "pnpm run package:fc && s deploy xenix-backend",
    "deploy:workers": "pnpm run build:workers && s deploy auto-tune-worker manual-tune-worker predict-worker",
    "deploy:all": "pnpm run package:fc && pnpm run build:workers && s deploy --all"
  }
}
```

---

### Phase 4: Frontend Integration

#### 4.1 Frontend Upload Flow

Create [packages/frontend/src/services/uploadService.ts](../../../packages/frontend/src/services/uploadService.ts):

```typescript
import { z } from 'zod';

const presignedUrlResponseSchema = z.object({
  url: z.string().url(),
  key: z.string(),
  expiresAt: z.string().datetime(),
});

export async function uploadDataset(file: File, datasetId: number) {
  // 1. Get presigned URL from backend
  const presignedResponse = await fetch('/api/data/upload-url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      key: `datasets/${datasetId}/${file.name}`,
      contentType: file.type,
      expiresIn: 3600,
    }),
  });

  const presigned = presignedUrlResponseSchema.parse(await presignedResponse.json());

  // 2. Upload directly to OSS
  const uploadResponse = await fetch(presigned.url, {
    method: 'PUT',
    headers: {
      'Content-Type': file.type,
    },
    body: file,
  });

  if (!uploadResponse.ok) {
    throw new Error('Upload to OSS failed');
  }

  // 3. Notify backend with metadata
  const metadataResponse = await fetch('/api/data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      storageKey: presigned.key,
      fileName: file.name,
      fileSize: file.size,
      datasetId,
    }),
  });

  return await metadataResponse.json();
}
```

---

### Phase 5: Testing & Verification

#### Local Testing

**1. Storage with Local Filesystem**:
```bash
cd packages/backend
STORAGE_TYPE=local pnpm dev

# Test presigned URL generation
curl -X POST http://localhost:3000/data/upload-url \
  -H "Content-Type: application/json" \
  -d '{"key": "datasets/1/test.xlsx", "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}'
```

**2. Python Worker Locally** (simulate FC invoke):
```bash
cd python-workers/auto_tune
python3 -c "
import index
event = {
  'taskId': 1,
  'inputFile': '../../uploads/datasets/1/test.xlsx',
  'model': 'regression.linear_regression',
  'featureColumns': ['col1'],
  'targetColumn': 'target'
}
result = index.handler(event, None)
print(result)
"
```

#### FC Environment Testing

**1. Deploy Layer**:
```bash
pnpm run build:layer
pnpm run deploy:layer
```

**2. Deploy Functions**:
```bash
# Deploy all
pnpm run deploy:all

# Or deploy individually
pnpm run deploy:backend
pnpm run deploy:workers
```

**3. Test OSS Mount**:
```bash
# Invoke backend to check mount
curl https://<function-url>/health

# Check logs for mount status
s logs -f xenix-backend
```

**4. Test Async Invocation**:
```bash
# Submit auto-tune task
curl -X POST https://<function-url>/tune/auto-tune \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"datasetId": 1, "model": "...", ...}'

# Check worker logs
s logs -f auto-tune-worker --tail
```

**5. Frontend Upload Test**:
- Upload file through frontend
- Verify file appears in OSS bucket
- Verify backend receives metadata
- Check dataset analysis succeeds

#### Verification Checklist

- [ ] Local storage works in development
- [ ] OSS presigned URLs generated correctly
- [ ] Frontend uploads directly to OSS
- [ ] Backend receives and validates metadata
- [ ] OSS mounted to backend function at `/mnt/oss`
- [ ] OSS mounted to worker functions at `/mnt/oss`
- [ ] Python layer uploaded and attached
- [ ] Backend invokes workers asynchronously
- [ ] Workers access files via mount point
- [ ] Python scripts execute successfully
- [ ] Task results written to OSS
- [ ] Download URLs work correctly

---

## Implementation Order

### Week 1: Storage Foundation
1. Implement Zod schemas for storage
2. Implement `StorageService` interface
3. Implement `LocalStorage` class
4. Update config with storage variables
5. Update dataset upload endpoint (presigned URL)
6. Test locally with local storage

**Deliverable**: Storage abstraction with presigned URLs

### Week 2: OSS Integration & Python Workers
1. Implement `OSSStorage` class
2. Create Python worker structure
3. Create Python worker handlers (index.py for each)
4. Create copy-ml-to-workers script
5. Create `FCInvokeService`
6. Test workers locally

**Deliverable**: Python workers ready for deployment

### Week 3: Layer & Deployment
1. Create build-python-layer script
2. Create s.yaml with all functions
3. Configure OSS mount in s.yaml
4. Build and upload Python layer
5. Deploy backend function
6. Deploy worker functions
7. Verify OSS mounts

**Deliverable**: All functions deployed with OSS mounted

### Week 4: Integration & Testing
1. Update task submission to use FC async invoke
2. Update frontend upload flow
3. Test end-to-end flow
4. Monitor logs and fix issues
5. Performance testing
6. Documentation

**Deliverable**: Fully working system with FC async tasks

---

## Rollback Strategy

### Storage Issues
- **Problem**: OSS errors, presigned URLs failing
- **Rollback**: Set `STORAGE_TYPE=local`, redeploy backend
- **Impact**: Backend handles uploads again (temporary)

### Worker Issues
- **Problem**: Python workers failing, import errors
- **Rollback**: Keep old Node.js ML execution with `setImmediate()`
- **Impact**: Back to inline execution temporarily

### Mount Issues
- **Problem**: OSS mount not working, permission errors
- **Rollback**: Use OSS SDK instead of mount (download to /tmp)
- **Impact**: Slower but functional

### Layer Issues
- **Problem**: Python package import errors
- **Rollback**: Include packages in worker code directly
- **Impact**: Larger deployment package

---

## Environment Variables Reference

### Local Development (.env)
```bash
STORAGE_TYPE=local
UPLOAD_DIR=./uploads
```

### FC Production (s.yaml)
```bash
NODE_ENV=production
BACKEND_PORT=9000
STORAGE_TYPE=oss
OSS_REGION=cn-hangzhou
OSS_ACCESS_KEY_ID=LTAI...
OSS_ACCESS_KEY_SECRET=...
OSS_BUCKET=xenix-data
OSS_MOUNT_POINT=/mnt/oss
DATABASE_URL=postgresql://...@rds.aliyuncs.com:5432/xenix
JWT_SECRET=...
PYTHON_PATH=/usr/bin/python3
```

---

## Critical Files Summary

### New Files to Create
- [src/storage/schemas.ts](../../../packages/backend/src/storage/schemas.ts) - Zod schemas for storage
- [src/storage/StorageService.ts](../../../packages/backend/src/storage/StorageService.ts) - Interface
- [src/storage/LocalStorage.ts](../../../packages/backend/src/storage/LocalStorage.ts) - Local impl
- [src/storage/OSSStorage.ts](../../../packages/backend/src/storage/OSSStorage.ts) - OSS impl
- [src/storage/index.ts](../../../packages/backend/src/storage/index.ts) - Factory
- [src/services/FCInvokeService.ts](../../../packages/backend/src/services/FCInvokeService.ts) - FC async invoke
- [python-workers/auto_tune/index.py](../../../packages/backend/python-workers/auto_tune/index.py) - Worker
- [python-workers/manual_tune/index.py](../../../packages/backend/python-workers/manual_tune/index.py) - Worker
- [python-workers/predict/index.py](../../../packages/backend/python-workers/predict/index.py) - Worker
- [scripts/build-python-layer.js](../../../packages/backend/scripts/build-python-layer.js) - Layer builder
- [scripts/copy-ml-to-workers.js](../../../packages/backend/scripts/copy-ml-to-workers.js) - ML script copier
- [s.yaml](../../../packages/backend/s.yaml) - Serverless-devs config

### Files to Modify
- [src/config/index.ts](../../../packages/backend/src/config/index.ts) - Add storage config with Zod
- [src/routes/datasets.ts](../../../packages/backend/src/routes/datasets.ts) - Presigned URLs
- [src/routes/download.ts](../../../packages/backend/src/routes/download.ts) - Presigned download URLs
- [src/routes/tune.ts](../../../packages/backend/src/routes/tune.ts) - FC async invoke
- [src/routes/predict.ts](../../../packages/backend/src/routes/predict.ts) - FC async invoke
- [src/utils/datasetUtils.ts](../../../packages/backend/src/utils/datasetUtils.ts) - Use filesystem path
- [package.json](../../../packages/backend/package.json) - Add scripts

### Files to Remove
- [src/jobs/mlTaskWorker.ts](../../../packages/backend/src/jobs/mlTaskWorker.ts) - BullMQ worker
- [src/jobs/mlTaskProcessor.ts](../../../packages/backend/src/jobs/mlTaskProcessor.ts) - BullMQ processor
- [src/queues/](../../../packages/backend/src/queues/) - BullMQ queue setup

---

## Success Metrics

### Technical Metrics
- [ ] Frontend uploads directly to OSS (0% backend bandwidth)
- [ ] Presigned URL generation < 100ms
- [ ] OSS mount accessible in all functions
- [ ] Python workers start < 3s (cold start)
- [ ] File access via mount < 200ms

### Operational Metrics
- [ ] One-command deployment: `pnpm run deploy:all`
- [ ] Layer updates independent of function code
- [ ] Clear logs for debugging
- [ ] Rollback in < 5 minutes

### Business Metrics
- [ ] ML tasks complete successfully
- [ ] No file size limits (OSS handles large files)
- [ ] Concurrent task processing
- [ ] Proper error handling
