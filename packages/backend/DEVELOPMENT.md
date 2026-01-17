# Backend Development Guide

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm 8+
- PostgreSQL 14+
- Docker & Docker Compose

### Setup

```bash
# From root directory
pnpm install

# Start database
docker-compose up -d

# Generate and apply migrations
pnpm run db:generate
pnpm run db:migrate

# Start backend dev server (port 3000)
pnpm dev:backend
```

Backend dev server runs on `http://localhost:3000`

## Development

### Start Dev Server

```bash
# With hot reload
pnpm dev:backend
```

Environment variables (in .env):

```bash
JWT_SECRET=your-secret-key-at-least-32-chars
DATABASE_URL=postgres://user:pass@localhost/xenix
FRONTEND_URL=http://localhost:5173
```

### Run Tests

```bash
pnpm test
pnpm test:watch
pnpm test:coverage
```

### Build & Run

```bash
# Development build (in-memory)
pnpm dev:backend

# Production build
pnpm build

# Run production build
pnpm start
```

## Database

### Migrations

```bash
# Generate migration from schema changes
pnpm run db:generate

# Apply migrations
pnpm run db:migrate

# Reset database (dev only)
pnpm run db:reset
```

## Build & Deployment

See [DEPLOYMENT.md](../../DEPLOYMENT.md) for:

- Production build steps
- Aliyun FC deployment
- Environment configuration
- Monitoring and security

### Local Production Test

```bash
# Build
pnpm build

# Run
pnpm start
# Server runs on http://localhost:3000
```

### Aliyun FC Deployment

```bash
pnpm build:fc
pnpm package:fc
pnpm deploy:backend
```

## Resources

- [Root DEVELOPMENT.md](../../DEVELOPMENT.md)
- [Backend Architecture](./ARCHITECTURE.md)
- [Hono Documentation](https://hono.dev/)
- [DrizzleORM Documentation](https://orm.drizzle.team/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
