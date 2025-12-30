/**
 * Core type definitions for the application
 */

export interface Dataset {
  id: number;
  projectId?: number;
  name: string;
  description?: string;
  fileName: string;
  fileSize: number;
  columns: string[];
  rowCount: number;
  createdAt: string;
}

export interface ModelOption {
  label: string;
  value: string;
}

export interface TuningMetrics {
  mse_train?: number;
  mae_train?: number;
  r2_train?: number;
  mse_test?: number;
  mae_test?: number;
  r2_test?: number;
}

export interface TuningResult {
  model: string;
  params?: Record<string, any>;
  metrics?: TuningMetrics;
  status?: TaskStatus;
  trainingType?: TrainingType;
  createdAt?: string | Date;
}

// Auto-tune task parameter type
export interface AutoTuneTaskParameter {
  model: string;
  datasetId: number;
  featureColumns: string[];
  targetColumn: string;
  paramGrid?: Record<string, any[]>; // Parameter grid with arrays of values
  trainingType: "auto";
}

// Manual-tune task parameter type
export interface ManualTuneTaskParameter {
  model: string;
  datasetId: number;
  featureColumns: string[];
  targetColumn: string;
  parameters: Record<string, any>; // Single parameter values
  trainingType: "manual";
  parentTaskId?: number; // Optional parent auto-tune task
}

// Auto-tune task result type
export interface AutoTuneTaskResult {
  params: Record<string, any>; // Best parameters found
  metrics: Record<string, any>;
  bestScore?: number;
}

// Manual-tune task result type
export interface ManualTuneTaskResult {
  params: Record<string, any>; // Parameters used
  metrics: Record<string, any>;
}

export interface TaskInfo {
  id: number;
  workItemId?: number;
  type: string; // 'auto-tune', 'tune', 'predict', etc.
  status: string;
  result?: AutoTuneTaskResult | ManualTuneTaskResult | any;
  parameter?: AutoTuneTaskParameter | ManualTuneTaskParameter | any;
  error?: string;
  createdAt?: string;
}

export interface TaskLog {
  level: string;
  message: string;
  timestamp: string;
}

export interface PredictionTask {
  taskId: number;
  status: string;
  outputFile?: string;
  error?: string;
}

export interface ColumnSelection {
  featureColumns: string[];
  targetColumn: string;
  datasetId?: number;
}

export type TrainingType = "auto" | "manual";

export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface WorkItem {
  id: number;
  projectId: number; // Required - work items must belong to a project
  name: string;
  description?: string;
  status: "active" | "completed" | "archived";
  // Upload step results - stored to skip upload step on return
  datasetId?: number; // Selected dataset from upload step
  featureColumns?: string[]; // Selected features
  targetColumn?: string; // Selected target column
  createdAt: string;
  updatedAt: string;
  tasks?: TaskInfo[]; // Populated when needed
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  status: "active" | "completed" | "archived";
  createdAt: string;
  updatedAt: string;
  workItems?: WorkItem[]; // Populated when needed
  datasets?: Dataset[]; // Populated when needed
}
