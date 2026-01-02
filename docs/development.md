# Development Guide

## Build for production

```bash
pnpm build
```

## Desktop (Electron)

- Dev (Electron shell + Nuxt dev server):

```bash
pnpm electron:dev
```

- Build Windows NSIS installer:

```bash
pnpm electron:build:win
```

Notes:

- Desktop build runs SPA mode (SSR disabled) with hash routing and relative assets for file://.
- Nuxt devtools are disabled in packaged builds.
- Application icon can be added later via electron-builder `win.icon` (see package.json).
- Preload exposes `window.electronAPI.openDialog(options)` for file dialogs.

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
