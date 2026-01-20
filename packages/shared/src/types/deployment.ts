/**
 * ML Backend Deployment type definitions
 */

export interface MLBackendDeployment {
  id: number;
  name: string;
  createdBy?: string; // UUID of the user who created the deployment (null means public)
  apiUrl: string;
  proxy?: string;
  storage: "local" | "oss"; // Storage type must match dataset storage
  createdAt: string;
}
