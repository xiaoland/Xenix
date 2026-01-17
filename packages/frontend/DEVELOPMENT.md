# Frontend Development Guide

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm 8+

### Setup

```bash
# From root directory
pnpm install
pnpm dev:frontend
```

Frontend dev server runs on `http://localhost:5173`

## Development

### Start Dev Server

```bash
pnpm dev:frontend
```

### Build for Production

```bash
pnpm build:frontend
```

### Preview Production Build

```bash
pnpm preview
```

## Environment Variables

Create `.env` in frontend directory:

```bash
# API endpoint
VITE_API_BASE=http://localhost:3000

# Environment
VITE_ENV=development
```

## Resources

- [Root DEVELOPMENT.md](../../DEVELOPMENT.md)
- [Frontend Architecture](./ARCHITECTURE.md)
- [Vue 3 Documentation](https://vuejs.org/)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Ant Design Vue](https://www.antdv.com/)
