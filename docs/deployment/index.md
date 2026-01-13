# Xenix Deployment Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Environment Variables](#environment-variables)
- [Database Management](#database-management)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Node.js**: 18.x or higher
- **pnpm**: 8.x or higher
- **Python**: 3.9 or higher
- **PostgreSQL**: 16.x or higher
- **Redis**: 7.x or higher (optional, for future job queue)
- **Docker & Docker Compose**: Latest version (optional, for containerized setup)

### Python Dependencies

The application requires several Python ML libraries:

```bash
pip install scikit-learn xgboost lightgbm pandas numpy openpyxl
```

Or use PDM (project uses PDM for Python dependency management):

```bash
pdm install
```

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/xiaoland/Xenix.git
cd Xenix
```

### 2. Install Node Dependencies

```bash
pnpm install
```

### 3. Setup Environment Variables

#### Root Environment (.env)

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
NODE_ENV=development
DATABASE_URL=postgresql://xenix:xenix_dev_password@localhost:5435/xenix
PYTHON_EXECUTABLE=python3
JWT_SECRET=your-super-secret-jwt-key-here-change-in-production
BACKEND_PORT=3000
FRONTEND_URL=http://localhost:5173
VITE_API_URL=http://localhost:3000
```

#### Backend Environment

```bash
cp packages/backend/.env.example packages/backend/.env
```

Edit `packages/backend/.env`:

```env
DATABASE_URL=postgresql://xenix:xenix_dev_password@localhost:5435/xenix
REDIS_URL=redis://localhost:6379
PYTHON_EXECUTABLE=python3
JWT_SECRET=your-super-secret-jwt-key-here
PORT=3000
FRONTEND_URL=http://localhost:5173
```

#### Frontend Environment

```bash
cp packages/frontend/.env.example packages/frontend/.env
```

Edit `packages/frontend/.env`:

```env
VITE_API_URL=http://localhost:3000
```

### 4. Start Database Services

Using Docker Compose (recommended):

```bash
pnpm docker:up
```

This starts:

- PostgreSQL on port 5435
- Redis on port 6379

Or manually install and start PostgreSQL and Redis on your system.

### 5. Run Database Migrations

```bash
pnpm db:migrate
```

### 6. Start Development Servers

Start both frontend and backend:

```bash
pnpm dev
```

Or start them separately:

```bash
# Terminal 1 - Backend
pnpm dev:backend

# Terminal 2 - Frontend
pnpm dev:frontend
```

Access the application:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:3000>
- Backend Health: <http://localhost:3000/health>

### 7. Run Tests

```bash
# Run all tests once
pnpm test

# Run tests in watch mode
pnpm test:watch

# Generate coverage report
pnpm test:coverage
```

## Production Deployment

### 1. Build the Application

```bash
# Build all packages
pnpm build

# Or build individually
pnpm build:backend
pnpm build:frontend
```

### 2. Setup Production Environment

Create production `.env` files with secure values:

**Backend `.env`:**

```env
NODE_ENV=production
DATABASE_URL=postgresql://user:password@production-db-host:5432/xenix
REDIS_URL=redis://production-redis-host:6379
PYTHON_EXECUTABLE=/path/to/production/python
JWT_SECRET=<STRONG-SECRET-KEY-MINIMUM-32-CHARS>
PORT=3000
FRONTEND_URL=https://your-domain.com
```

**Frontend build time environment:**

```env
VITE_API_URL=https://api.your-domain.com
```

### 3. Deploy Backend

#### Option A: Direct Node.js

```bash
cd packages/backend
node dist/index.js
```

#### Option B: PM2 (Process Manager)

```bash
npm install -g pm2

# Start backend with PM2
cd packages/backend
pm2 start dist/index.js --name xenix-backend

# Save PM2 configuration
pm2 save

# Setup PM2 to start on system boot
pm2 startup
```

### 4. Deploy Frontend

The frontend is a static application after build. Deploy `packages/frontend/dist` to any static hosting:

#### Option A: Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/Xenix/packages/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

#### Option B: Vercel

```bash
cd packages/frontend
vercel --prod
```

Set environment variable in Vercel dashboard:

- `VITE_API_URL`: Your backend API URL

#### Option C: Netlify

```bash
cd packages/frontend
netlify deploy --prod --dir=dist
```

Set environment variable in Netlify dashboard:

- `VITE_API_URL`: Your backend API URL

## Docker Deployment

### Development with Docker Compose

```bash
# Start all services (PostgreSQL + Redis)
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Remove volumes (WARNING: deletes data)
docker compose down -v
```

### Production Docker Setup (Future)

A production-ready Dockerfile for the application is planned but not yet implemented. Current docker-compose.yml only includes PostgreSQL and Redis services.

## Environment Variables

### Backend Variables

| Variable            | Description                  | Required | Default                |
| ------------------- | ---------------------------- | -------- | ---------------------- |
| `NODE_ENV`          | Environment mode             | Yes      | development            |
| `PORT`              | Backend server port          | No       | 3000                   |
| `DATABASE_URL`      | PostgreSQL connection string | Yes      | -                      |
| `REDIS_URL`         | Redis connection string      | No       | redis://localhost:6379 |
| `JWT_SECRET`        | Secret for JWT tokens        | Yes      | -                      |
| `PYTHON_EXECUTABLE` | Path to Python               | Yes      | python3                |
| `FRONTEND_URL`      | Frontend URL for CORS        | Yes      | <http://localhost:5173>  |

### Frontend Variables

| Variable       | Description          | Required | Default               |
| -------------- | -------------------- | -------- | --------------------- |
| `VITE_API_URL` | Backend API base URL | Yes      | <http://localhost:3000> |

## Database Management

### Migrations

```bash
# Generate new migration
pnpm db:generate

# Apply migrations
pnpm db:migrate
```

### Backup and Restore

#### Backup

```bash
pg_dump -h localhost -p 5435 -U xenix -d xenix > backup.sql
```

#### Restore

```bash
psql -h localhost -p 5435 -U xenix -d xenix < backup.sql
```

### Database Monitoring

```bash
# Check database status
docker compose exec postgres psql -U xenix -d xenix -c "\dt"

# View table sizes
docker compose exec postgres psql -U xenix -d xenix -c "
  SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

## Troubleshooting

### Common Issues

#### Issue: Port 5432 already in use

**Solution**: The docker-compose.yml uses port 5435 to avoid conflicts. If this is still occupied:

```bash
# Check what's using the port
lsof -i :5435

# Change the port in docker-compose.yml and .env files
```

#### Issue: Python scripts failing

**Solution**: Ensure Python dependencies are installed:

```bash
# Check Python path
which python3

# Install dependencies
pip install scikit-learn xgboost lightgbm pandas numpy openpyxl

# Update PYTHON_EXECUTABLE in .env
```

#### Issue: Module not found errors

**Solution**: Ensure all packages are built:

```bash
pnpm install
pnpm build
```

#### Issue: Database connection errors

**Solution**:

1. Verify PostgreSQL is running: `docker compose ps`
2. Check connection string in `.env`
3. Test connection: `psql $DATABASE_URL`

#### Issue: CORS errors

**Solution**:

1. Check `FRONTEND_URL` in backend `.env`
2. Check `VITE_API_URL` in frontend `.env`
3. Ensure URLs match exactly (no trailing slashes)

#### Issue: Build fails in frontend

**Solution**:

```bash
cd packages/frontend
rm -rf node_modules dist
pnpm install
pnpm build
```

### Logs

#### Backend Logs

```bash
# Development
pnpm dev:backend

# Production with PM2
pm2 logs xenix-backend

# Docker
docker compose logs -f
```

#### Frontend Logs

Frontend is static after build. Check browser console for runtime errors.

### Performance Monitoring

#### Database Performance

```bash
# Check slow queries
docker compose exec postgres psql -U xenix -d xenix -c "
  SELECT
    query,
    calls,
    total_time,
    mean_time
  FROM pg_stat_statements
  ORDER BY mean_time DESC
  LIMIT 10;
"
```

#### Application Metrics

Consider adding monitoring tools:

- **Prometheus** + **Grafana** for metrics
- **Sentry** for error tracking
- **PM2 Monitoring** for process health

## Security Checklist

Before deploying to production:

- [ ] Change `JWT_SECRET` to a strong random string (32+ characters)
- [ ] Use strong database passwords
- [ ] Enable HTTPS/SSL certificates
- [ ] Configure firewall rules
- [ ] Set up database backups
- [ ] Enable rate limiting (future feature)
- [ ] Review and secure environment variables
- [ ] Use secrets management (AWS Secrets Manager, etc.)
- [ ] Enable database connection pooling
- [ ] Configure Redis authentication if exposed

## Support

For issues and questions:

- GitHub Issues: <https://github.com/xiaoland/Xenix/issues>
- Documentation: See `docs/` directory
- Architecture: See `ARCHITECTURE.md` and `docs/plan/monorepo-refactor-vite-vue-hono.md`
