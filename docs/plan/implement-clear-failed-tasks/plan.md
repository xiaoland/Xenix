# Plan: Implement Clear Failed Tasks Feature

## Overview

The `handleClearFailedTasks` function in `TuningStep.vue` is currently a placeholder. The backend endpoint `DELETE /api/tasks/failed` is already implemented, so we need to update the frontend to call it.

## Current State

- Backend: `DELETE /api/tasks/failed` endpoint exists and takes `workItemId` query parameter
- Frontend: Placeholder function shows "Task deletion feature coming soon"

## Implementation Steps

1. **Update handleClearFailedTasks function**
   - Replace placeholder with actual API call to `client.tasks.failed.$delete`
   - Pass `workItemId` as query parameter
   - Handle success/error responses appropriately
   - Refresh task list after successful deletion

2. **Update button behavior** (optional)
   - Consider changing button disabled condition to check for failed tasks instead of all tasks
   - But current implementation is acceptable as backend handles empty results gracefully

## Files to Modify

- `packages/frontend/src/components/ml/tuning/TuningStep.vue`

## Testing

- Manual testing: Create failed tasks, click clear button, verify tasks are removed
- API testing: Verify endpoint works correctly

## Validation

- Run frontend build to ensure no TypeScript errors
- Test the feature in the UI
