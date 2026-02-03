# Datasets Feature

## Status: ✅ Active

## Overview

Dataset management for uploading and organizing training data.

## User Stories

- As a user, I want to upload CSV files as datasets
- As a user, I want to view all my uploaded datasets
- As a user, I want to preview dataset contents
- As a user, I want to delete old datasets

## Acceptance Criteria

1. CSV file upload with drag-and-drop
2. Dataset list with metadata (rows, columns, size)
3. Dataset preview (first N rows)
4. Dataset selection in work item creation
5. Delete dataset with confirmation

## Technical Notes

- File upload via multipart/form-data
- Datasets stored in `datasets/` directory
- Metadata extracted and stored in database
- Supported formats: CSV (TSV planned)

## Related

- Frontend: `packages/frontend/src/features/datasets/`
- Backend: `/api/datasets` endpoints
- Storage: `datasets/` directory
