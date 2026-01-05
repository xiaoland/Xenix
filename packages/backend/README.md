# Xenix Backend (Hono API)

Backend API server for Xenix ML platform, built with Hono framework.

## Setup

1. **Install dependencies:**
   ```bash
   pnpm install
   ```

2. **Configure environment variables:**
   
   Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` with your configuration:
   - `DATABASE_URL`: PostgreSQL connection string
   - `JWT_SECRET`: Secret key for JWT token signing
   - `PYTHON_EXECUTABLE`: Path to Python executable (default: python3)
   - `PORT`: Server port (default: 3000)
   - `FRONTEND_URL`: Frontend URL for CORS (default: http://localhost:5173)
   
   > **Note**: This backend uses Node.js native `.env` file support (Node.js >= 20.6.0) via the `--env-file` flag. No additional packages like `dotenv` are needed.

3. **Run database migrations:**
   ```bash
   pnpm db:generate  # Generate migration files
   pnpm db:migrate   # Apply migrations
   ```

## Development

Start the development server with hot reload:

```bash
pnpm dev
```

The server will start on `http://localhost:3000` (or the PORT specified in .env).

## Build

Build for production:

```bash
pnpm build
```

## Production

Run the production build:

```bash
pnpm start
```

## API Endpoints

### Authentication
- `POST /api/auth/signin` - User sign in
- `POST /api/auth/signup` - User sign up

### Projects
- `GET /api/projects` - List user's projects
- `POST /api/projects` - Create project
- `GET /api/projects/:id` - Get project details
- `PUT /api/projects/:id` - Update project
- `DELETE /api/projects/:id` - Delete project

### Work Items
- `GET /api/work-items` - List work items
- `POST /api/work-items` - Create work item
- `GET /api/work-items/:id` - Get work item details
- `PUT /api/work-items/:id` - Update work item
- `DELETE /api/work-items/:id` - Delete work item

### Datasets
- `GET /api/data` - List datasets
- `POST /api/data` - Upload dataset
- `GET /api/data/:id` - Get dataset details
- `DELETE /api/data/:id` - Delete dataset

### Models
- `GET /api/models` - List available ML models
- `GET /api/models/:name` - Get model details

### Tasks
- `GET /api/tasks` - List tasks
- `GET /api/tasks/:id` - Get task details
- `DELETE /api/tasks/failed` - Delete failed tasks
- `DELETE /api/tasks/:model` - Delete tasks by model

### Training
- `POST /api/auto-tune` - Start auto-tune training
- `POST /api/manual-tune` - Start manual-tune training

### Prediction
- `POST /api/predict/inline` - Inline prediction with JSON data

### Results
- `GET /api/download/:id` - Download prediction results
- `GET /api/obsrv/:id` - Get task observation logs

## Environment Variables

Required environment variables:

- `DATABASE_URL` - PostgreSQL connection string (required)
- `JWT_SECRET` - Secret key for JWT tokens (required)
- `PYTHON_EXECUTABLE` - Python executable path (optional, default: python3)
- `PORT` - Server port (optional, default: 3000)
- `FRONTEND_URL` - Frontend URL for CORS (optional, default: http://localhost:5173)
