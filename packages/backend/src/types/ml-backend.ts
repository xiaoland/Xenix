/**
 * ML Backend deployment types and interfaces
 */

export type MLBackendDeploymentType = 'http' | 'http-proxy-frontend';

/**
 * ML Backend Deployment database model
 */
export interface MLBackendDeployment {
  id: number;
  name: string;
  created_by: string | null; // UUID
  deployment_type: MLBackendDeploymentType;
  deployment_params: DeploymentParams;
  is_default: boolean;
  is_active: boolean;
  created_at: Date;
  updated_at: Date;
}

/**
 * HTTP deployment configuration parameters
 */
export interface DeploymentParams {
  apiUrl: string; // HTTP endpoint URL
  proxy?: string; // HTTP proxy URL or 'frontend://this'
  basePath?: string; // Base path for file operations
}

/**
 * Legacy: Spawn adapter configuration parameters (for backwards compatibility during migration)
 */
export interface SpawnAdapterParams {
  pythonPath?: string; // Path to Python executable (default: 'python3')
  mlBackendPath?: string; // Path to ml-backend main.py (default: auto-detect)
  basePath?: string; // Base path for file operations (passed as --base-path)
}

/**
 * Legacy: Aliyun Function Compute adapter configuration parameters (for backwards compatibility during migration)
 */
export interface AliyunFCAdapterParams {
  serviceName: string; // FC service name (e.g., 'xenix')
  timeout?: number; // Invocation timeout in milliseconds (default: 60000)
  basePath?: string; // Base path on FC side (e.g., '/mnt/oss')
}

/**
 * DTO for creating a new ML backend deployment
 */
export interface CreateMLBackendDeploymentDTO {
  name: string;
  created_by?: string | null; // UUID of user who created this deployment
  deployment_type: MLBackendDeploymentType;
  deployment_params: DeploymentParams;
  is_default?: boolean;
  is_active?: boolean;
}

/**
 * DTO for updating an existing ML backend deployment
 */
export interface UpdateMLBackendDeploymentDTO {
  name?: string;
  deployment_params?: DeploymentParams;
  is_default?: boolean;
  is_active?: boolean;
}
