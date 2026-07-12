# Xenix Website

Standalone Xenix website for Cloudflare Pages plus a Cloudflare Worker API.
The root path `/` is the public Xenix homepage.

## Required Runtime Configuration

`XENIX_DOWNLOAD_URL` is required. It has no default value by design.

Local development:

```sh
cp .env.example .dev.vars
pnpm install
pnpm run dev
pnpm run dev:worker
```

Production GitHub Actions variables:

- `XENIX_DOWNLOAD_URL`
- `XENIX_PAGES_PROJECT_NAME`
- `XENIX_WORKER_NAME`
- `XENIX_WORKER_ROUTE`, for example `example.com/api/*`
- `XENIX_D1_DATABASE_NAME`
- `XENIX_D1_DATABASE_ID`
- `CLOUDFLARE_WORKERS_SUBDOMAIN`, required for preview Worker URLs

Production GitHub Actions secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Optional variables:

- `VITE_API_ORIGIN`: set when the page should call a Worker origin instead of same-origin `/api`.
- `VITE_SITE_URL`: public site origin used by future metadata expansion.
- `XENIX_PREVIEW_WORKER_PREFIX`: preview Worker prefix. Defaults to `xenix-website`.
- `XENIX_WORKER_ZONE_NAME`: Cloudflare zone name for the Worker route when Wrangler cannot infer it.

## D1

Create a D1 database, then configure its name and id in GitHub Actions variables.

Apply migrations before production traffic:

```sh
pnpm run build:worker
pnpm exec wrangler d1 migrations apply "$XENIX_D1_DATABASE_NAME" --remote --config .wrangler-worker-dry-run.toml
```

## Checks

```sh
XENIX_DOWNLOAD_URL="https://downloads.example.cn/Xenix-Setup.exe" pnpm run check
```

The check command fails if `XENIX_DOWNLOAD_URL` is missing.
