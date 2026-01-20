# Deployment Guide

## Deployment Architectures

### Development

```
Local Machine
├── Frontend (Vite dev server, port 5173)
├── Backend (tsx watch, port 3000)
├── PostgreSQL (docker-compose)
└── Redis (docker-compose)
```

**Setup**:

```bash
docker-compose up -d
pnpm dev:backend &
pnpm dev:frontend
```

### Production

```
Aliyun Cloud
├── Frontend: CDN (static files)
├── Backend: Aliyun FC (serverless)
├── Database: Aliyun RDS PostgreSQL
├── Storage: Aliyun OSS (file storage)
└── ML Worker: FC Function (ml-backend)
```

## Building for Deployment

### Production Build

```bash
# Build all packages
pnpm build

# Frontend production build
pnpm -F @xenix/frontend build
# Output: dist/

# Backend production build
pnpm -F @xenix/backend build
# Output: dist/index.js

# Note: @xenix/shared uses source dependencies pattern
# No separate build step needed - consumed directly from TypeScript source
```

### Aliyun FC Deployment

```bash
# Deploy backend to FC
cd packages/backend
pnpm run deploy

# Deploy ml-backend to FC
cd packages/ml-backend
pnpm run deploy
```

## Environment Configuration

### Backend Environment Variables

```bash
# Database
DATABASE_URL=postgres://user:pass@host/xenix

# Authentication
JWT_SECRET=your-secret-key-at-least-32-chars

# CORS & Frontend
FRONTEND_URL=https://your-domain.com
CORS_ORIGIN=https://your-domain.com

# File Storage
STORAGE_TYPE=oss|local
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
OSS_BUCKET=xenix-data
OSS_ACCESS_KEY_ID=your-access-key
OSS_ACCESS_KEY_SECRET=your-secret-key

# ML Backend
PYTHON_PATH=/usr/bin/python3
ML_TIMEOUT=300000
ML_ADAPTER_TYPE=spawn|aliyun-fc

# Redis (for job queue)
REDIS_HOST=redis-host
REDIS_PORT=6379
```

### Frontend Environment Variables

```bash
# API endpoint
VITE_API_BASE=https://api.your-domain.com

# Environment
VITE_ENV=production
```

## Aliyun FC Deployment

### Prerequisites

- Aliyun account with FC service enabled
- RAM role with FC, RDS, OSS permissions
- Aliyun CLI configured

### Deployment Steps

```bash
# 1. Configure Aliyun credentials
aliyun configure

# 2. Deploy backend
cd packages/backend
pnpm run deploy

# 3. Deploy ml-backend
cd packages/ml-backend
pnpm run deploy

# 4. Deploy frontend
cd packages/frontend
pnpm run build
# Upload dist/ to OSS or CDN
```

### FC Configuration

Trigger types:

- **HTTP Trigger** (Backend): Exposed as REST API
- **Event Trigger** (ML Backend): Invoked from backend
- **Scheduled Trigger** (optional): Cleanup jobs

Memory: 512MB minimum for backend, 1GB+ for ml-backend
Timeout: 30 seconds for HTTP, 5 minutes for async

## Database Deployment

### RDS PostgreSQL Setup

```sql
-- Create database
CREATE DATABASE xenix;

-- Create user
CREATE USER xenix_user WITH PASSWORD 'strong-password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE xenix TO xenix_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO xenix_user;
```

### Apply Migrations

```bash
# Generate migration files
pnpm run db:generate

# Apply to production database
DATABASE_URL=postgres://user:pass@host/xenix pnpm run db:migrate
```

## OSS Setup (Aliyun)

```bash
# Create bucket
aliyun oss mb oss://xenix-data

# Configure CORS (for direct uploads)
# Upload CORS configuration

# Create directories
aliyun oss mkdir oss://xenix-data/datasets/
aliyun oss mkdir oss://xenix-data/ml-backend/
```

### GitHub Actions Example

```yaml
name: Deploy

on:
  push:
    branches: [master]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'pnpm'
      
      - run: pnpm install
      - run: pnpm build
      - run: pnpm test
      
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: |
          # Deploy frontend to CDN
          # Deploy backend to FC
          # Deploy ml-backend to FC
```

## Monitoring & Logging

### Aliyun FC Logs

```bash
# View function logs
aliyun fc logs --function-name xenix-backend --max-items 100

# Stream logs
aliyun fc logs --function-name xenix-backend --follow
```

### Database Monitoring

- Use Aliyun RDS console to monitor:
  - Query performance
  - Storage usage
  - Connection count
  - Slow queries

### Error Tracking

- Configure error logging to:
  - Database (task_logs table)
  - Aliyun SLS (Simple Log Service)
  - Third-party services (Sentry, etc.)

## Security Considerations

### Network

- Enable VPC for RDS
- Configure security groups for FC
- Use private endpoints where possible

### Authentication

- Rotate JWT_SECRET regularly
- Use strong database passwords
- Enable MFA for Aliyun account

### Data

- Enable encryption at rest for RDS
- Enable encryption in transit (SSL/TLS)
- Regularly backup database
- Restrict OSS bucket access with policies

### Secrets Management

```bash
# Store sensitive values in:
# - Aliyun Secrets Manager
# - FC environment variables
# - Not in Git or source code

# Example: Store in Aliyun Secrets Manager
aliyun secretsmanager create-secret \
  --name xenix-jwt-secret \
  --secret-data "your-secret-key"
```

## Rollback Procedures

### Backend Rollback

```bash
# Deploy previous version
aliyun fc update-function \
  --function-name xenix-backend \
  --code <previous-version-code>
```

### Database Rollback

```bash
# Revert last migration
pnpm run db:rollback

# Restore from backup
# (Use Aliyun RDS backup/restore)
```

### Frontend Rollback

```bash
# Switch CDN origin to previous build
# (Configure in Aliyun CDN console)
```

## Performance Optimization

### Frontend

- Enable gzip compression
- Minify and bundle assets
- Use CDN for static files
- Implement service workers for offline support
- Optimize images

### Backend

- Enable database connection pooling
- Cache frequently accessed data
- Optimize database indexes
- Use pagination for large result sets
- Implement request rate limiting

### Database

- Create indexes on frequently queried columns
- Archive old data
- Optimize query performance
- Regular vacuum and analyze

### ML Backend

- Use model quantization for smaller sizes
- Cache predictions when possible
- Implement timeout handling
- Monitor FC resource usage

## Troubleshooting

### FC Deployment Issues

```bash
# Check function status
aliyun fc get-function --function-name xenix-backend

# Check recent errors
aliyun fc logs --function-name xenix-backend --since 1h

# Redeploy function
pnpm deploy:backend
```

### Database Connection Issues

- Verify DATABASE_URL format
- Check VPC security group rules
- Verify RDS is accessible from FC

### OSS Access Issues

- Verify bucket permissions
- Check OSS_ACCESS_KEY_ID and_SECRET
- Verify bucket region matches endpoint

## Disaster Recovery

### Backup Strategy

- **Database**: Daily automated backups (Aliyun RDS)
- **Files**: Regular sync to secondary OSS bucket
- **Code**: Git repository with tags for releases

### Recovery Procedures

1. **Database Loss**: Restore from latest backup
2. **File Loss**: Restore from secondary OSS bucket
3. **Code Issues**: Revert to previous Git tag and redeploy

### Testing Recovery

- Monthly: Test database restore
- Quarterly: Full disaster recovery drill
- Document runbooks for each scenario

## Release Management

### Versioning

Use semantic versioning: `MAJOR.MINOR.PATCH`

- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

### Release Process

```bash
# Create release branch
git checkout -b release/v1.2.0

# Update version in package.json files
# Update CHANGELOG.md

# Create tag
git tag -a v1.2.0 -m "Release v1.2.0"

# Push and create release
git push origin release/v1.2.0
git push origin v1.2.0
```

## Resources

- [Development Guide](./DEVELOPMENT.md)
- [Root Architecture](./ARCHITECTURE.md)
- [Aliyun FC Documentation](https://www.alibabacloud.com/help/en/fc/)
- [Aliyun RDS Documentation](https://www.alibabacloud.com/help/en/rds/)
