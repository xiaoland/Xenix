# Xenix Monorepo

This is a monorepo containing the Xenix ML Platform packages.

## Structure

```
packages/
├── backend/     # Hono API server
├── frontend/    # Vite + Vue 3 SPA
└── shared/      # Shared TypeScript types
```

## Development

### Prerequisites

- Node.js 18+
- pnpm 9+
- PostgreSQL 14+
- Python 3.12+ (for ML operations)

### Setup

1. Install dependencies:

```bash
pnpm install
```

2. Configure environment:

```bash
# Backend
cp packages/backend/.env.example packages/backend/.env
# Edit packages/backend/.env with your database credentials
```

3. Setup database:

```bash
pnpm db:generate
pnpm db:migrate
```

### Running in Development

Run both frontend and backend concurrently:

```bash
pnpm dev
```

Or run them separately:

```bash
# Terminal 1 - Backend (http://localhost:3000)
pnpm dev:backend

# Terminal 2 - Frontend (http://localhost:5173)
pnpm dev:frontend
```

### Building for Production

```bash
pnpm build
```

## Packages

### Backend (`@xenix/backend`)

Hono-based API server with:

- RESTful API endpoints
- PostgreSQL database with DrizzleORM
- JWT authentication
- Python ML script execution
- Background task processing

**Tech Stack**: Hono, DrizzleORM, PostgreSQL, Node.js

### Frontend (`@xenix/frontend`)

Vite + Vue 3 single-page application with:

- Vue Router for routing
- Pinia for state management
- Ant Design Vue for UI components
- UnoCSS for styling
- Vue I18n for internationalization

**Tech Stack**: Vite, Vue 3, Ant Design Vue, UnoCSS

### Shared (`@xenix/shared`)

Common TypeScript types and utilities shared between frontend and backend.

## Migration from Nuxt.js

This project was migrated from a Nuxt.js fullstack application to a monorepo structure. Key changes:

- **Frontend**: Nuxt.js SSR/SSG → Vite + Vue 3 SPA
- **Backend**: Nitro → Hono
- **Structure**: Monolithic → Monorepo

Benefits:

- Faster build times with Vite
- Independent deployment of frontend and backend
- Clearer separation of concerns
- Lightweight backend with Hono
