-- Add custom HTTP headers column to ml_backend_deployments table
-- This allows configuring custom headers (e.g., authentication tokens) for ML backend API requests
ALTER TABLE "ml_backend_deployments" ADD COLUMN "headers" jsonb;
