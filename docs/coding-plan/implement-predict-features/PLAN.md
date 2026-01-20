# Implementation Plan: Predict on File and Predict Inline

## Overview
Implement both file-based and inline prediction features in the PredictionStep component.

## Current Status
- **Inline Prediction**: Already implemented but needs verification
- **File Prediction**: Not implemented (throws error)

## Implementation Tasks

### 1. Backend Implementation
- [x] Add `FilePredictSchema` to shared schemas
- [x] Add `FilePredictDto` type export
- [x] Implement `POST /api/predict/file` endpoint
  - File upload handling (FormData)
  - File validation (Excel/CSV, max 10MB)
  - Save uploaded file to uploads directory
  - Create prediction task record
  - Call `predictFile()` business logic function
  - Return task ID

### 2. Frontend Implementation
- [x] Update `PredictionStep.vue` to implement file upload
  - Replace placeholder error with actual implementation
  - Create FormData with file and parameters
  - Call `/api/predict/file` endpoint
  - Handle response and errors
  - Display prediction task result

### 3. API Integration
**File Prediction Flow:**
1. User uploads Excel/CSV file
2. Frontend sends file via FormData to `/api/predict/file`
3. Backend saves file and creates task
4. Backend calls Python script `predict_on_file.py`
5. Task status updated as prediction runs
6. Results saved to output file
7. Frontend displays results via PredictionResult component

**Inline Prediction Flow:**
1. User enters data in table
2. Frontend sends JSON array to `/api/predict/inline`
3. Backend creates task with inline data
4. Backend calls Python script `predict_on_json.py`
5. Task status updated as prediction runs
6. Results saved to output file
7. Frontend displays results via PredictionResult component

## Technical Details

### Backend Route Parameters
**File Prediction (`/api/predict/file`):**
- `file`: File (multipart/form-data)
- `workItemId`: number (form field)
- `model`: string (form field)
- `tuningTaskId`: number (form field)

**Inline Prediction (`/api/predict/inline`):**
- `workItemId`: number (JSON)
- `model`: string (JSON)
- `tuningTaskId`: number (JSON)
- `predictionData`: array of objects (JSON)

### File Storage
- Prediction input files: `uploads/prediction_input_{workItemId}_{timestamp}_{filename}`
- Prediction output files:
  - File mode: `uploads/file_prediction_{workItemId}_{taskId}_{timestamp}.xlsx`
  - Inline mode: `uploads/inline_prediction_{workItemId}_{taskId}_{timestamp}.xlsx`

### Python Scripts
- `predict_on_file.py`: File-based prediction
- `predict_on_json.py`: Inline data prediction

## Dependencies
- Existing `predictFile` and `predictInline` functions in `backend/src/business/ml/index.ts`
- Existing Python prediction scripts
- PredictionResult component for displaying results

## Success Criteria
1. Users can upload Excel/CSV files for batch prediction
2. Users can enter data manually in a table for inline prediction
3. Both methods create prediction tasks successfully
4. Prediction results are displayed correctly
5. Error handling works properly for invalid files or data
6. File size limits are enforced (10MB)
7. File type validation works (Excel/CSV only)
