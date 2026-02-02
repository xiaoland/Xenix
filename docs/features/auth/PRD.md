# Auth Feature

## Status: ✅ Active

## Overview

User authentication and authorization system for Xenix platform.

## User Stories

- As a user, I want to sign up with email/password so I can create an account
- As a user, I want to sign in so I can access my projects and data
- As a user, I want to stay signed in across sessions

## Acceptance Criteria

1. Sign-up form validates email format and password strength
2. Sign-in authenticates against backend API
3. Auth token persists in localStorage
4. Protected routes redirect to sign-in when not authenticated

## Technical Notes

- Uses Pinia store for client-side auth state
- JWT tokens stored in localStorage
- Hono RPC client includes auth headers automatically

## Related

- Frontend: `packages/frontend/src/features/auth/`
- Backend: Authentication middleware in Hono app
