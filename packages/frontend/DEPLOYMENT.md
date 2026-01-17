# Frontend Deployment Guide

## Building for Production

### Build Steps

```bash
# Build frontend
pnpm -F @xenix/frontend build

# Output: dist/
# - index.html
# - assets/
# - js files
# - css files
```

### Optimize Build

```bash
# Minification, code splitting, tree shaking are automatic
# Check build size
pnpm -F @xenix/frontend build --report

# Preview production build locally
pnpm -F @xenix/frontend preview
```

## Deployment Options

### Option 1: Aliyun OSS + CDN

```bash
# 1. Build
pnpm -F @xenix/frontend build

# 2. Upload to OSS
aliyun oss cp -r dist/ oss://xenix-data/frontend/

# 3. Configure CDN in Aliyun console
# - Accelerate: oss://xenix-data/frontend/
# - Cache rules:
#   - 1 hour for index.html
#   - 7 days for assets/
# - HTTPS: Enable with certificate
```

### Option 2: Static Hosting Service

Upload `dist/` directory to:

- Vercel
- Netlify
- GitHub Pages
- AWS S3 + CloudFront
- Other CDN services

### Option 3: Self-Hosted

```bash
# Build
pnpm -F @xenix/frontend build

# Serve with web server (nginx, Apache)
# Point to dist/ directory
```

## Environment Configuration

### Production Environment Variables

Create `.env.production`:

```bash
# API endpoint
VITE_API_BASE=https://api.your-domain.com

# Environment
VITE_ENV=production

# Optional: analytics, error tracking
VITE_SENTRY_DSN=https://your-sentry-key@sentry.io/project-id
```

## Performance Optimization

## Resources

- [Root DEPLOYMENT.md](../../DEPLOYMENT.md)
- [Frontend Development](./DEVELOPMENT.md)
- [Frontend Architecture](./ARCHITECTURE.md)
- [Vite Deployment Guide](https://vitejs.dev/guide/static-deploy.html)
