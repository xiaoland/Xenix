# Projects Feature

## Status: ✅ Active

## Overview

Project management system for organizing ML work items.

## User Stories

- As a user, I want to create projects to organize my ML experiments
- As a user, I want to view all my projects on a dashboard
- As a user, I want to edit project details
- As a user, I want to delete projects I no longer need

## Acceptance Criteria

1. Project list displays all user projects
2. Create project modal with name and description
3. Edit project inline or via modal
4. Delete project with confirmation
5. Projects show associated work items count

## Technical Notes

- TanStack Query for server state management
- Optimistic updates for better UX
- Projects are top-level organizational units

## Related

- Frontend: `packages/frontend/src/features/projects/`
- Backend: `/api/projects` endpoints
