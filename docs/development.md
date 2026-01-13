# Development Guide

## Build for production

```bash
pnpm build
```

## Run production build

```bash
node .output/server/index.mjs
```

## Database management

```bash
# Open Drizzle Studio
pnpm db:studio

# Generate new migration
pnpm db:generate

# Apply migration
pnpm db:migrate
```
