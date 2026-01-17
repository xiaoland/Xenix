-- Rename ml_backend_workers table to ml_backend_deployments
ALTER TABLE ml_backend_workers RENAME TO ml_backend_deployments;

-- Rename columns for clarity
ALTER TABLE ml_backend_deployments RENAME COLUMN adapter TO deployment_type;
ALTER TABLE ml_backend_deployments RENAME COLUMN adapter_params TO deployment_params;

-- Update check constraint
ALTER TABLE ml_backend_deployments DROP CONSTRAINT IF EXISTS ml_backend_workers_adapter_check;
ALTER TABLE ml_backend_deployments ADD CONSTRAINT ml_backend_deployments_type_check
  CHECK (deployment_type IN ('http', 'http-proxy-frontend'));

-- Rename unique constraint
ALTER TABLE ml_backend_deployments DROP CONSTRAINT IF EXISTS ml_backend_workers_name_unique;
ALTER TABLE ml_backend_deployments ADD CONSTRAINT ml_backend_deployments_name_unique UNIQUE (name);

-- Update foreign key reference name
ALTER TABLE ml_backend_deployments DROP CONSTRAINT IF EXISTS ml_backend_workers_created_by_users_id_fk;
ALTER TABLE ml_backend_deployments ADD CONSTRAINT ml_backend_deployments_created_by_users_id_fk
  FOREIGN KEY (created_by) REFERENCES users(id);

-- Rename indexes
DROP INDEX IF EXISTS idx_ml_backend_workers_adapter;
DROP INDEX IF EXISTS idx_ml_backend_workers_default;
CREATE INDEX idx_ml_backend_deployments_type ON ml_backend_deployments(deployment_type);
CREATE INDEX idx_ml_backend_deployments_default ON ml_backend_deployments(is_default) WHERE is_default = true;

-- Update tasks table foreign key column name
ALTER TABLE tasks RENAME COLUMN ml_backend_worker_id TO ml_backend_deployment_id;

-- Rename tasks table index
DROP INDEX IF EXISTS idx_tasks_worker;
CREATE INDEX idx_tasks_deployment ON tasks(ml_backend_deployment_id);

-- Update foreign key constraint
ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_ml_backend_worker_id_ml_backend_workers_id_fk;
ALTER TABLE tasks ADD CONSTRAINT tasks_ml_backend_deployment_id_ml_backend_deployments_id_fk
  FOREIGN KEY (ml_backend_deployment_id) REFERENCES ml_backend_deployments(id);

-- Update existing seed data to use HTTP deployment type
UPDATE ml_backend_deployments
SET
  deployment_type = 'http',
  deployment_params = jsonb_build_object(
    'apiUrl', 'http://localhost:8000'
  )
WHERE name = 'local-spawn';

UPDATE ml_backend_deployments
SET
  deployment_type = 'http',
  deployment_params = jsonb_build_object(
    'apiUrl', 'https://ml-backend.example.com'
  )
WHERE name = 'aliyun-fc-prod';
