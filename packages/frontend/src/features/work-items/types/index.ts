/**
 * Work Items Types
 *
 * Feature-specific type definitions for work item management
 */

/**
 * Work item entity
 */
export interface WorkItem {
  id: string;
  projectId: string;
  name: string;
  description?: string;
  status: WorkItemStatus;
  datasetId?: string;
  targetColumn?: string;
  featureColumns?: string[];
  modelType?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Work item status
 */
export type WorkItemStatus =
  | "draft"
  | "preparing"
  | "prepared"
  | "tuning"
  | "tuned"
  | "predicting"
  | "completed"
  | "failed";

/**
 * Create work item input
 */
export interface CreateWorkItemInput {
  name: string;
  description?: string;
  datasetId?: string;
  targetColumn?: string;
  featureColumns?: string[];
  modelType?: string;
}

/**
 * Update work item input
 */
export interface UpdateWorkItemInput {
  name?: string;
  description?: string;
  status?: WorkItemStatus;
  datasetId?: string;
  targetColumn?: string;
  featureColumns?: string[];
  modelType?: string;
}

/**
 * Work item list response
 */
export interface WorkItemListResponse {
  workItems: WorkItem[];
  total: number;
}

/**
 * Work item step
 */
export type WorkItemStep = "prepare" | "tune" | "predict";

/**
 * Work item step configuration
 */
export interface WorkItemStepConfig {
  step: WorkItemStep;
  label: string;
  description: string;
  isComplete: boolean;
  isActive: boolean;
}
