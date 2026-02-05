# Xenix Backend Deployment to Aliyun FC (Current Workflow)

This document describes the **actual backend deployment path used in this repository**.

> Scope: `packages/backend` Node.js API on Aliyun Function Compute (custom runtime), with Node.js dependencies delivered by a custom FC layer.

## Overview

Current deployment model:

- Runtime: `custom.debian12` (Node.js 22 available via official layer)
- Function startup command: `./fc-start.sh`
- Application artifact deployed to function code (`/code`):
  - `dist/`
  - `fc-start.sh`
  - `s.yaml` (deployment template)
- Node.js dependencies (`@hono/node-server`, etc.) are published separately to custom layer `xenix-backend-nodejs-deps` and mounted to `/opt/nodejs/node_modules`.

This keeps function code minimal and avoids shipping workspace files.

---

## Source of Truth Files

- Workflow: `.github/workflows/deploy-backend.yml`
- Layer builder: `.github/workflow/build-layer-backend.sh`
- FC template: `packages/backend/s.yaml`
- Startup script: `packages/backend/fc-start.sh`
- Backend build config: `packages/backend/tsup.config.ts`

---

## Runtime Behavior

`fc-start.sh` does three key things:

1. Prepends `/opt/nodejs/bin` to `PATH`
2. Creates symlink: `./node_modules -> /opt/nodejs/node_modules`
3. Starts backend with `node dist/index.js`

Why symlink is needed:

- Backend output is ESM (`dist/index.js`), and ESM does not use `NODE_PATH` fallback for package resolution.
- Therefore, `node_modules` must exist in the function working directory.

---

## Layer Build and Publish

Layer is built in isolated temporary workspace by `.github/workflow/build-layer-backend.sh`:

- Reads `packages/backend/package.json`
- Filters out `workspace:*` deps
- Installs prod deps only (`npm install --omit=dev --ignore-scripts`)
- Produces layer directory at `packages/backend/layer/nodejs/node_modules`
- Fails fast if `@hono/node-server` is missing

Workflow then publishes with Serverless Devs:

```bash
s layer publish \
  --layer-name xenix-backend-nodejs-deps \
  --code packages/backend/layer \
  --compatible-runtime nodejs22,custom.debian12 \
  --region <region>
```

After publish, workflow parses new layer version and updates `packages/backend/s.yaml` layer ARN.

---

## Function Artifact Preparation (Minimal)

Before function deploy, workflow creates a minimal directory:

`packages/backend/.fc-deploy`

Containing only:

- `dist/`
- `fc-start.sh`
- `s.yaml`

Then deploy is executed from `.fc-deploy` so `code: .` in `s.yaml` points to this minimal artifact.

---

## CI/CD Flow (deploy-backend)

On each run, workflow does:

1. `pnpm install --frozen-lockfile`
2. Install/configure Serverless Devs credentials
3. Build backend layer (`build-layer-backend.sh`)
4. Publish layer
5. Update `packages/backend/s.yaml` with new layer version
6. Commit layer version update (if changed)
7. Prune old layer versions
8. Build backend (`pnpm --filter @xenix/backend run build`)
9. Prepare minimal function artifact (`.fc-deploy`)
10. Deploy function from `.fc-deploy`

---

## Required Aliyun Configuration

In `packages/backend/s.yaml`, ensure:

- `runtime: custom.debian12`
- `customRuntimeConfig.command: ["./fc-start.sh"]`
- Layers include:
  - official Node.js 22 layer
  - custom `xenix-backend-nodejs-deps` layer version
- Environment variables are set (`DATABASE_URL`, `JWT_SECRET`, OSS settings, etc.)

---

## Troubleshooting

### `ERR_MODULE_NOT_FOUND: Cannot find package '@hono/node-server'`

Check in order:

1. Layer contains package under `nodejs/node_modules/@hono/node-server`
2. Function has latest custom layer version attached
3. Function code package does **not** include unexpected workspace payload that interferes with symlink behavior
4. `fc-start.sh` is executable and startup command is `./fc-start.sh`

### `operation not permitted` at startup

Usually indicates runtime filesystem operation issue.

- Verify startup script path and permissions
- Verify function code package layout is minimal and expected
- Verify FC runtime has permissions/paths exactly as configured

### Layer version not updated

Workflow expects publish output to include version metadata; if parsing fails, deployment should fail fast.

---

## Manual Local Verification Pattern

From repo root:

```bash
pnpm --filter @xenix/backend run build
bash .github/workflow/build-layer-backend.sh
```

Then simulate FC runtime by placing layer deps under `/opt/nodejs/node_modules` and running `fc-start.sh` from a minimal directory containing only `dist/` and `fc-start.sh`.

---

## Notes

- Keep backend output ESM unless runtime strategy changes holistically.
- Keep `@xenix/shared` bundled via tsup (`noExternal: ["@xenix/shared"]`).
- Avoid adding workspace artifacts into function code package.
