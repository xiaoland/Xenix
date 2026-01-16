/**
 * ML Backend adapter types and interfaces
 */

export type MLBackendAdapterType = 'aliyun-fc' | 'spawn';

/**
 * ML Backend Worker database model
 */
export interface MLBackendWorker {
  id: number;
  name: string;
  created_by: string | null; // UUID
  adapter: MLBackendAdapterType;
  adapter_params: Record<string, any>;
  is_default: boolean;
  is_active: boolean;
  created_at: Date;
  updated_at: Date;
}

/**
 * Spawn adapter configuration parameters
 */
export interface SpawnAdapterParams {
  pythonPath?: string; // Path to Python executable (default: 'python3')
  mlBackendPath?: string; // Path to ml-backend main.py (default: auto-detect)
  basePath?: string; // Base path for file operations (passed as --base-path)
}

/**
 * Aliyun Function Compute adapter configuration parameters
 */
export interface AliyunFCAdapterParams {
  serviceName: string; // FC service name (e.g., 'xenix')
  timeout?: number; // Invocation timeout in milliseconds (default: 60000)
  basePath?: string; // Base path on FC side (e.g., '/mnt/oss')
}

/**
 * DTO for creating a new ML backend worker
 */
export interface CreateMLBackendWorkerDTO {
  name: string;
  created_by?: string | null; // UUID of user who created this worker
  adapter: MLBackendAdapterType;
  adapter_params: SpawnAdapterParams | AliyunFCAdapterParams;
  is_default?: boolean;
  is_active?: boolean;
}

/**
 * DTO for updating an existing ML backend worker
 */
export interface UpdateMLBackendWorkerDTO {
  name?: string;
  adapter_params?: SpawnAdapterParams | AliyunFCAdapterParams;
  is_default?: boolean;
  is_active?: boolean;
}
