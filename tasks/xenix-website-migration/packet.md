# Xenix Website Migration

## Objective & Hypothesis

- Objective: migrate the Xenix website surface from `xiaoland/xiaoland` into this repository as an independent deployable website folder.
- Hypothesis: the target should be implemented as a standalone TypeScript Cloudflare project, preserving the source `/xenix` page behavior while improving maintainability for this repo.

## Guardrails Touched

- Root `AGENTS.md`: ask for explicit start before modifying code; task packet and exploration are free.
- Current route: `Intent`, because the repo will gain a new public website/deployment surface.
- Current mode: `Explore`.
- Implementation taste loaded because the work affects topology, build boundaries, deployment contracts, and backend state.

## Source Evidence

- Requested source branch `xiaoland/xiaoland new-fix-xenix` is now available.
- `git ls-remote` reports `new-fix-xenix` at `3f3e09f226c5d9cee9b66a6925a43c7713ce9247`.
- The `new-fix-xenix` branch contains Xenix website behavior, but not as a top-level `/xenix` folder.
- Relevant source files on `new-fix-xenix`:
  - `src/pages/xenix.ts`
  - `src/templates/xenix.ts`
  - `src/templates/sections/xenix-download.ts`
  - `public/assets/xenix.css`
  - `public/images/xenix/*.png`
  - `src/worker/index.ts`
  - `src/db/schema/xenix.ts`
  - `drizzle/0001_xenix_download_users.sql`
  - `.github/workflows/ci.yml`
  - `.github/workflows/deploy-production.yml`
  - `.github/workflows/deploy-preview.yml`
  - `wrangler.worker.toml`
  - `docs/deployment.md`

## Current Understanding

- Page behavior:
  - static Xenix landing/download page
  - screenshot carousel with three images
  - three feature cards
  - HTMX form for email or phone contact
  - backend returns a fixed download URL
- Backend behavior in source:
  - Worker exposes `/api/health`
  - Worker exposes `POST /api/xenix/download`
  - source validates email or China mainland phone number
  - source writes parsed email or phone to D1 table `xenix_download_users`
  - source uses `onConflictDoNothing` for duplicate contacts
  - source returns fixed download URL `https://r2.lanzhijiang.dev/xenix-latest.zip`
  - user confirmed this URL should remain the default, but should be configurable through GitHub Repository Actions variable / Worker environment
- Current repo:
  - no existing GitHub Actions workflows except issue template
  - Python/PDM native app project, so website should remain isolated from native app packaging
  - current git worktree has unrelated existing modifications

## Candidate Implementation Shape

- Added a standalone folder `website/`, containing:
  - Vite static site for Cloudflare Pages
  - Worker entry for `/api/*`
  - D1 migration for download leads
  - `wrangler.worker.toml`
  - package scripts for `dev`, `build`, `check`, `deploy:*`
  - local docs for Cloudflare secrets, D1 setup, and deployment
- Added root GitHub Actions workflows scoped to `website/**`:
  - CI/check on PR
  - production deploy: check, D1 migrations, Worker, Pages
  - preview deploy: preview Worker, Pages preview
- Model `XENIX_DOWNLOAD_URL` as Worker environment configuration:
  - required explicit configuration, with no runtime fallback
  - GitHub Actions variable `XENIX_DOWNLOAD_URL` should pass through during Worker deploy
  - local development must configure the value explicitly, for example through Wrangler vars or a local `.dev.vars` file that stays uncommitted
  - missing value should fail clearly instead of silently using a default

## Open Questions

- Confirm production Cloudflare names:
  - Pages project name
  - Worker name
  - production domain or Pages subdomain
  - D1 database name/id

## Implementation Notes

- Frontend:
  - `website/src/main.ts`
  - `website/src/styles.css`
  - copied Xenix screenshots under `website/public/images/xenix/`
  - `/` is the public homepage
- Backend:
  - `website/src/worker/index.ts`
  - `GET /api/health`
  - `POST /api/xenix/download`
  - validates email or China mainland phone number
  - writes deduplicated contact records to D1 table `xenix_download_contacts`
  - requires `XENIX_DOWNLOAD_URL`, no default fallback
- Deployment:
  - `.github/workflows/website-ci.yml`
  - `.github/workflows/website-deploy-production.yml`
  - `.github/workflows/website-deploy-preview.yml`
  - `website/scripts/run-worker.ts` generates Wrangler config and injects required Worker vars
  - deploy workflow runs Worker before Pages

## Verification

- `pnpm install` in `website/`
- `XENIX_DOWNLOAD_URL="https://r2.lanzhijiang.dev/xenix-latest.zip" pnpm run check`
  - typecheck passed
  - Vite build passed
  - `verify:dist` passed
  - Wrangler Worker dry-run passed and showed `env.XENIX_DOWNLOAD_URL ("(hidden)")`
- `pnpm run build:worker` without `XENIX_DOWNLOAD_URL`
  - failed with `XENIX_DOWNLOAD_URL must be configured explicitly.`
- Local D1 migration:
  - `pnpm exec wrangler d1 migrations apply xenix-website --local --config .wrangler-worker-dry-run.toml`
  - production workflow uses `--config .wrangler-worker-dry-run.toml` so Wrangler reads `migrations_dir = "drizzle"`
- Local service checks:
  - `GET http://127.0.0.1:5173/xenix/` returned `200`
  - `GET http://127.0.0.1:8787/api/health` returned configured health JSON
  - invalid form input showed `请填写有效的邮箱或中国大陆手机号。`
  - valid API POST returned configured download URL
  - D1 query confirmed `xenix-test@example.com` persisted with `contact_type = email`
- Browser:
  - desktop `1366x768` inspected with `agent-browser`; first viewport and interactive elements rendered
  - mobile `390x844` inspected with `agent-browser`; hero, carousel, feature section, and controls rendered without overlap

## Next Step

User must configure GitHub Actions variables/secrets and real Cloudflare D1 database id/name before production deploy.
