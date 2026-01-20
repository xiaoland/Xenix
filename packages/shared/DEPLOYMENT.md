# Shared Package Deployment Guide

## Overview

The shared package contains:

- Zod validation schemas
- TypeScript type definitions
- Constants
- Error types

These are bundled with frontend and backend during their builds.

## Deployment

**No direct deployment needed** - shared package is consumed by frontend and backend.

### Build Order

When deploying changes that include shared package updates:

```bash
# 1. Build shared
pnpm -F @xenix/shared build

# 2. Rebuild backend
pnpm -F @xenix/backend build

# 3. Rebuild frontend
pnpm -F @xenix/frontend build

# 4. Deploy both (backend first, then frontend)
```

## Version Management

### Bumping Version

```bash
# 1. Update version in packages/shared/package.json
{
  "version": "1.0.1",
  ...
}

# 2. Rebuild dependents
pnpm -F @xenix/backend build
pnpm -F @xenix/frontend build

# 3. Tag in git
git tag -a v1.0.1 -m "Release v1.0.1"
```

## Breaking Changes

When making breaking changes to shared package:

```bash
# 1. Update schemas and types with deprecation warnings
/**
 * @deprecated Use NewSchema instead, will be removed in v2.0.0
 */
export const OldSchema = z.object({ /* ... */ })

# 2. Update frontend and backend to use new schema
# 3. Test both packages
# 4. Deploy backend first
# 5. Deploy frontend second
```

## Type Safety Verification

Before deployment, verify type safety:

```bash
# Check backend types
pnpm -F @xenix/backend type-check

# Check frontend types
pnpm -F @xenix/frontend type-check

# Run tests
pnpm -F @xenix/shared test
pnpm -F @xenix/backend test
pnpm -F @xenix/frontend test
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Deploy

on:
  push:
    branches: [master]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'pnpm'
      
      - run: pnpm install
      - run: pnpm build
      - run: pnpm test
      - run: pnpm type-check

  deploy-backend:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pnpm deploy:backend

  deploy-frontend:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pnpm deploy:frontend
```

## Troubleshooting

### Type Errors After Deployment

```bash
# Rebuild packages
pnpm clean
pnpm install
pnpm build

# Verify types
pnpm type-check
```

### Frontend/Backend Out of Sync

```bash
# Ensure shared is built first
cd packages/shared && pnpm build

# Rebuild frontend and backend
cd ../frontend && pnpm build
cd ../backend && pnpm build
```

## Resources

- [Root DEPLOYMENT.md](../../DEPLOYMENT.md)
- [Shared Development](./DEVELOPMENT.md)
- [Shared Architecture](./ARCHITECTURE.md)
