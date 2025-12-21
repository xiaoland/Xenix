# Testing the Python ML Pipeline Wrapper

This document provides instructions for manually testing the Python ML pipeline wrapper with both local and Docker execution modes.

## Prerequisites

1. PostgreSQL database running (via `docker compose up -d postgres`)
2. Node.js dependencies installed (`pnpm install`)
3. Database migrations applied

## Test 1: Local Execution Mode

### Setup

1. Ensure Python 3.12 is installed locally
2. Install Python dependencies:
   ```bash
   pdm install
   ```

3. Configure `.env`:
   ```
   PYTHON_EXECUTION_MODE=local
   PYTHON_EXECUTABLE=python3
   ```

### Test Hyperparameter Tuning

1. Start the development server:
   ```bash
   pnpm dev
   ```

2. Upload a training dataset via the UI or API:
   ```bash
   curl -X POST http://localhost:3000/api/upload \
     -F "file=@/path/to/training_data.xlsx" \
     -F "model=Ridge" \
     -F "featureColumns=[\"col1\",\"col2\",\"col3\"]" \
     -F "targetColumn=target"
   ```

3. Check logs for:
   - `[taskId] Execution mode: local`
   - Python script execution logs
   - Task completion status

4. Verify results in database:
   ```bash
   psql -h localhost -U xenix -d xenix_db -c "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 1;"
   psql -h localhost -U xenix -d xenix_db -c "SELECT * FROM model_results ORDER BY created_at DESC LIMIT 1;"
   ```

### Test Prediction

1. After tuning completes, make a prediction:
   ```bash
   curl -X POST http://localhost:3000/api/predict \
     -F "file=@/path/to/prediction_data.xlsx" \
     -F "trainingDataPath=/path/to/training_data.xlsx" \
     -F "model=Ridge" \
     -F "tuningTaskId=<task-id-from-tuning>" \
     -F "featureColumns=[\"col1\",\"col2\",\"col3\"]" \
     -F "targetColumn=target"
   ```

2. Verify output file is created with predictions

## Test 2: Docker Execution Mode

### Setup

1. Build and start the Python ML container:
   ```bash
   docker compose up -d python-ml
   ```

2. Verify the container is running:
   ```bash
   docker ps | grep xenix-python-ml
   ```

3. Configure `.env`:
   ```
   PYTHON_EXECUTION_MODE=docker
   ```

4. Restart the development server to pick up the new environment variable

### Test Hyperparameter Tuning

1. Upload a training dataset (same as Test 1)

2. Check logs for:
   - `[taskId] Execution mode: docker`
   - Docker container execution
   - Python script execution logs
   - Task completion status

3. Verify the Python script ran inside the container:
   ```bash
   docker logs xenix-python-ml
   ```

### Test Prediction

1. Make a prediction (same as Test 1)

2. Verify output file is created with predictions

## Expected Behavior

### Both Modes Should:

1. ✅ Execute Python scripts successfully
2. ✅ Parse structured JSON output from Python
3. ✅ Store results in PostgreSQL database
4. ✅ Update task status (pending → running → completed/failed)
5. ✅ Generate logs in OpenTelemetry format
6. ✅ Create output files with predictions

### Mode-Specific Behavior:

- **Local Mode**: Python runs directly on host machine
- **Docker Mode**: Python runs inside `xenix-python-ml` container with file paths adjusted

## Troubleshooting

### Local Mode Issues

- Python not found: Install Python 3.12 or update `PYTHON_EXECUTABLE` in `.env`
- Missing dependencies: Run `pdm install`
- Permission errors: Check file permissions on uploads directory

### Docker Mode Issues

- Container not running: Run `docker compose up -d python-ml`
- Build failures: Check `Dockerfile.python` and rebuild with `docker compose build python-ml`
- File access errors: Verify volume mounts in `docker-compose.yml`

## Verification Checklist

- [ ] Local mode: Tuning completes successfully
- [ ] Local mode: Prediction completes successfully
- [ ] Docker mode: Tuning completes successfully
- [ ] Docker mode: Prediction completes successfully
- [ ] Results stored correctly in database (both modes)
- [ ] Output files created (both modes)
- [ ] Logs captured correctly (both modes)
