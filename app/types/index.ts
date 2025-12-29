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

export interface TaskInfo {
  id: number;
  workItemId?: number;
  status: string;
  result?: any;
  parameter?: any;
  error?: string;
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
  status: 'active' | 'completed' | 'archived';
  createdAt: string;
  updatedAt: string;
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  status: 'active' | 'completed' | 'archived';
  createdAt: string;
  updatedAt: string;
  workItems?: WorkItem[]; // Populated when needed
  datasets?: Dataset[]; // Populated when needed
}
