# Xenix Aliyun FC Deployment - TODO List

## ✅ Phase 1: Storage Abstraction Layer (COMPLETED)

- [x] Create Zod schemas for storage operations
  - [x] OSSConfig schema
  - [x] FileMetadata schema
  - [x] PresignedUrlRequest/Response schemas
- [x] Create StorageService interface
  - [x] generatePresignedUploadUrl()
  - [x] generatePresignedDownloadUrl()
  - [x] exists(), delete(), stat()
  - [x] getFilesystemPath()
  - [x] copy()
- [x] Implement LocalStorage class
  - [x] Presigned URLs (fake for local dev)
  - [x] File operations on local filesystem
- [x] Implement OSSStorage class
  - [x] Real presigned URLs via ali-oss SDK
  - [x] OSS mounted filesystem support
- [x] Create storage factory
  - [x] Auto-select based on STORAGE_TYPE
  - [x] Validate OSS config with Zod
- [x] Update config with storage variables
  - [x] STORAGE_TYPE enum
  - [x] OSS_* configuration variables
  - [x] OSS_MOUNT_POINT
- [x] Install ali-oss dependency
- [x] Update dataset routes
  - [x] Add POST /upload-url endpoint
  - [x] Keep existing upload endpoint for backward compatibility
- [x] Update download route
  - [x] OSS: redirect to presigned URL
  - [x] Local: serve file directly
- [x] Build and verify no TypeScript errors

## ✅ Phase 2: Python ML Workers (COMPLETED)

- [x] Create python-workers directory structure
  - [x] auto_tune/
  - [x] manual_tune/
  - [x] predict/
- [x] Create FC handler for auto-tune worker
  - [x] index.py with handler()
  - [x] Event parsing and validation
  - [x] Error handling
  - [x] requirements.txt
- [x] Create FC handler for manual-tune worker
  - [x] index.py with handler()
  - [x] Event parsing and validation
  - [x] Error handling
  - [x] requirements.txt
- [x] Create FC handler for predict worker
  - [x] index.py with handler()
  - [x] Event parsing and validation
  - [x] Error handling
  - [x] requirements.txt
- [x] Create copy-ml-to-workers.js script
  - [x] Copy ML Python scripts to each worker
  - [x] Filter out TypeScript and test files
  - [x] Test script execution

## ✅ Phase 3: FC Async Task Integration (COMPLETED)

- [x] Install @alicloud/fc2 dependency
- [x] Create FCInvokeService
  - [x] Initialize FC client with credentials
  - [x] invokeAsync() method
  - [x] Zod schema for invoke request
  - [x] Error handling
  - [x] Graceful fallback for local mode
- [x] Update tune.ts routes
  - [x] Replace setImmediate() with FC async invoke (auto-tune)
  - [x] Replace setImmediate() with FC async invoke (manual-tune)
  - [x] Pass storage keys instead of file paths
  - [x] Update to use getFilesystemPath() for OSS mount paths
  - [x] Dual-mode operation (local dev + FC production)
- [x] Update predict.ts routes
  - [x] Replace setImmediate() with FC async invoke
  - [x] Pass storage keys for training data
  - [x] Generate output storage key
  - [x] Dual-mode output path handling
- [x] Build and verify no TypeScript errors

**Note**: Kept BullMQ dependencies for potential future use. ML functions in business/ml/index.ts kept for local development mode.

## ✅ Phase 4: Python Layer & Deployment Automation (COMPLETED)

- [x] Create build-python-layer.js script
  - [x] Create python-layer/ directory structure
  - [x] pip install to python/lib/python3.10/site-packages
  - [x] Use requirements.txt from workers
- [x] Create s.yaml for serverless-devs
  - [x] xenix-python-layer resource
  - [x] xenix-backend function (Node.js HTTP)
  - [x] auto-tune-worker function (Python)
  - [x] manual-tune-worker function (Python)
  - [x] predict-worker function (Python)
  - [x] Configure OSS NAS mount for all functions
  - [x] Environment variables configuration
- [x] Update package.json scripts
  - [x] build:layer
  - [x] build:workers (runs copy-ml-to-workers)
  - [x] deploy:layer
  - [x] deploy:backend
  - [x] deploy:workers
  - [x] deploy:all
- [x] Update .env.fc.example with OSS and NAS configuration
- [x] Create deployment documentation (DEPLOYMENT.md)

## 🧪 Phase 5: Testing & Verification (PENDING)

### Local Testing

- [ ] Test storage with local filesystem
  - [ ] Generate presigned URL
  - [ ] Verify fake URL format
  - [ ] Test file operations
- [ ] Test Python workers locally
  - [ ] Run auto-tune worker with test event
  - [ ] Run manual-tune worker with test event
  - [ ] Run predict worker with test event
- [ ] Test backend build
  - [ ] Run `pnpm run build`
  - [ ] Verify no TypeScript errors

### FC Deployment Testing

- [ ] Build and upload Python layer
  - [ ] Run build:layer
  - [ ] Deploy layer to Aliyun FC
  - [ ] Verify layer ARN
- [ ] Deploy backend function
  - [ ] Run package:fc
  - [ ] Deploy via s.yaml
  - [ ] Test health endpoint
  - [ ] Verify OSS mount
- [ ] Deploy worker functions
  - [ ] Copy ML scripts to workers
  - [ ] Deploy all workers
  - [ ] Verify Python layer attached
  - [ ] Verify OSS mount
- [ ] Test end-to-end flow
  - [ ] Generate presigned URL
  - [ ] Upload file to OSS (via curl or Postman)
  - [ ] Create dataset metadata via API
  - [ ] Submit ML task
  - [ ] Verify worker processes task
  - [ ] Check worker logs
  - [ ] Download result via presigned URL

## 📝 Phase 6: Documentation (PENDING)

- [ ] Update deployment guide
  - [ ] Storage configuration
  - [ ] OSS setup instructions
  - [ ] Python layer creation
  - [ ] Worker deployment
- [ ] Create environment variable reference
  - [ ] Local development (.env)
  - [ ] FC production (s.yaml)
- [ ] Add troubleshooting section
  - [ ] Common OSS mount issues
  - [ ] Python import errors
  - [ ] FC async invocation debugging
- [ ] Update README with deployment commands

## 🔄 Optional Enhancements (FUTURE)

- [ ] Frontend integration
  - [ ] Update upload service to use presigned URLs
  - [ ] Direct OSS upload from browser
  - [ ] Progress tracking
- [ ] Monitoring and logging
  - [ ] CloudWatch/FC logs integration
  - [ ] Error alerting
  - [ ] Performance metrics
- [ ] Optimize cold starts
  - [ ] Pre-warm functions
  - [ ] Optimize layer size
- [ ] Database schema updates
  - [ ] Store storage keys instead of file paths
  - [ ] Add storageType field to datasets table
- [ ] Migration script
  - [ ] Migrate existing files to OSS
  - [ ] Update file paths to storage keys in DB

---

## Current Status

**Last Updated**: UTC+8 2026-01-14 23:30

**Completed**:
- ✅ Phase 1: Storage Abstraction Layer
- ✅ Phase 2: Python ML Workers
- ✅ Phase 3: FC Async Task Integration
- ✅ Phase 4: Python Layer & Deployment Automation

**In Progress**: Phase 5 (Testing & Verification)

**Next Action**: Test deployment automation and verify FC deployment

**Deployment Ready**: Backend can now be deployed to Aliyun FC using `pnpm run deploy:all`

**Blockers**: None

**Key Files Created**:
- [s.yaml](../../packages/backend/s.yaml) - Serverless-devs configuration
- [DEPLOYMENT.md](../../packages/backend/DEPLOYMENT.md) - Deployment guide
- [.env.fc.example](../../packages/backend/.env.fc.example) - Environment variable template
- Package.json scripts for automated deployment
