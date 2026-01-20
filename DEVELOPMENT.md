# Development Guide

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm 8+
- PostgreSQL 14+
- Python 3.8+
- Docker & Docker Compose (for database services)

### Initial Setup

```bash
# Install dependencies
pnpm install

# Setup environment variables
cp .env.example .env

# Start database services
docker-compose up -d

# Generate and apply database migrations
pnpm run db:generate
pnpm run db:migrate
```

## Development Servers

### Backend

```bash
# Start backend dev server (port 3000)
pnpm dev:backend

# Environment variables (in .env)
JWT_SECRET=your-secret-key-at-least-32-chars
DATABASE_URL=postgres://user:pass@localhost/xenix
FRONTEND_URL=http://localhost:5173
```

### Frontend

```bash
# Start frontend dev server (port 5173)
pnpm dev:frontend
```

### ML Backend

```bash
# Build ml-backend
pnpm -F @xenix/ml-backend build

# Run locally
node dist/index.js < input.json
```

## Package Development

### Shared Package

Build shared types first when dependencies change:

```bash
cd packages/shared && pnpm build
cd packages/backend && pnpm build:shared
```

### Backend Development

```bash
# Dev server with hot reload
pnpm dev:backend

# Run tests
pnpm test

# Run tests in watch mode
pnpm test:watch

# Generate coverage report
pnpm test:coverage

# Build for production
pnpm build

# Start production build
pnpm start
```

### Frontend Development

```bash
# Dev server
pnpm dev:frontend

# Build for production
pnpm build:frontend

# Preview production build
pnpm preview
```

### ML Backend Development

```bash
# Build
pnpm -F @xenix/ml-backend build

# Run locally with JSON input
node dist/index.js < input.json

# Run tests
pnpm -F @xenix/ml-backend test
```

## Code Style & Conventions

### Frontend

- **Files**: kebab-case (useProjects.ts, ProjectCard.vue)
- **Components**: PascalCase (ProjectCard, WorkItemForm)
- **Composables**: camelCase starting with "use" (useProjects, useFormatters)
- **Script**: Use `<script setup lang="ts">` with Composition API

### Backend

- **Routes**: Explicit routing in `src/routes/`
- **Services**: Business logic in `src/services/`
- **Repositories**: Data access in `src/repositories/`
- **Middleware**: Request processing in `src/middleware/`
- **Error Handling**: Use custom error classes from `src/errors/`

### Shared

- **Schemas**: Define validation schemas with Zod
- **Types**: Export TypeScript types alongside schemas
- **Naming**: Use `{Entity}Schema` for Zod schemas, `{Entity}` for types

## Testing

### Running Tests

```bash
# Run all tests
pnpm test

# Run specific package tests
pnpm -F @xenix/backend test
pnpm -F @xenix/frontend test

# Watch mode
pnpm test:watch

# Coverage report
pnpm test:coverage
```

### Writing Tests

- **Vitest**: Used for unit tests in all packages
- **@vue/test-utils**: For Vue component testing
- **Location**: `__tests__/` folders in each package
- **Pattern**: Test files named `*.test.ts` or `*.spec.ts`

## Database Management

### Migrations

```bash
# Generate migration from schema changes
pnpm run db:generate

# Apply pending migrations
pnpm run db:migrate

# Reset database (development only)
pnpm run db:reset
```

### Database Schema

Edit schema in: `packages/backend/src/database/schema.ts`

Supported operations:

- Create tables
- Add/modify columns
- Create indexes
- Define relationships

## Git Workflow

### Branch Naming

- `feat/feature-name` - New features
- `fix/bug-name` - Bug fixes
- `docs/doc-name` - Documentation
- `refactor/refactor-name` - Code refactoring
- `test/test-name` - Test additions

### Commit Messages

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Before Submitting PR

```bash
# Run linter
pnpm run lint

# Run tests
pnpm test

# Build all packages
pnpm build

# Check for type errors
pnpm type-check
```

## Common Tasks

### Add a New API Endpoint

1. Create schema in `packages/shared/src/schemas/`
2. Add route handler in `packages/backend/src/routes/`
3. Create repository method in `packages/backend/src/repositories/`
4. Create composable in `packages/frontend/src/composables/`
5. Use composable in component via `<script setup>`

### Add a New Database Table

1. Add schema in `packages/backend/src/database/schema.ts`
2. Run `pnpm run db:generate` to create migration
3. Run `pnpm run db:migrate` to apply
4. Create repository for data access
5. Create service layer for business logic

### Add a New Page

1. Create component in `packages/frontend/src/views/`
2. Add route in `packages/frontend/src/router/`
3. Create composables for data fetching
4. Add corresponding API endpoints in backend

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps

# Restart database
docker-compose down
docker-compose up -d

# Check connection string in .env
DATABASE_URL=postgres://user:pass@localhost:5432/xenix
```

### Port Already in Use

```bash
# Frontend (default 5173)
pnpm dev:frontend -- --port 5174

# Backend (default 3000)
PORT=3001 pnpm dev:backend
```

### Module Not Found

```bash
# Reinstall dependencies
pnpm install

# Clear cache
pnpm store prune
```

### Build Failures

```bash
# Clear build artifacts
pnpm -F @xenix/backend clean
pnpm -F @xenix/frontend clean
pnpm -F @xenix/ml-backend clean

# Rebuild all
pnpm build
```

## Environment Variables

### Required (.env)

```bash
# Database
DATABASE_URL=postgres://user:password@localhost:5432/xenix

# Backend
JWT_SECRET=your-secret-key-at-least-32-chars
FRONTEND_URL=http://localhost:5173
PORT=3000

# ML Backend
PYTHON_PATH=/usr/bin/python3
ML_TIMEOUT=300000
```

### Optional

```bash
# File Storage
STORAGE_TYPE=local  # or 'oss'

# Aliyun OSS (if STORAGE_TYPE=oss)
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=xenix-data
OSS_ACCESS_KEY_ID=xxx
OSS_ACCESS_KEY_SECRET=xxx

# Redis (for job queue)
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Useful Commands

```bash
# Check TypeScript errors
pnpm type-check

# Lint code
pnpm lint

# Format code
pnpm format

# Build all packages
pnpm build

# Run specific package commands
pnpm -F @xenix/backend dev
pnpm -F @xenix/frontend build
pnpm -F @xenix/ml-backend test

# Update dependencies
pnpm update

# Check outdated packages
pnpm outdated
```

## Resources

- [Root Architecture](./ARCHITECTURE.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Frontend Architecture](./packages/frontend/ARCHITECTURE.md)
- [Backend Architecture](./packages/backend/ARCHITECTURE.md)
- [ML Backend Architecture](./packages/ml-backend/ARCHITECTURE.md)
