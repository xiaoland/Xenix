/**
 * Core type definitions for the application
 */

export interface Dataset {
  id: number;
  datasetId: string;
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
  status?: string;
  trainingType?: string;
  createdAt?: string | Date;
}

export interface TaskInfo {
  id: number;
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
  datasetId?: string;
}

export type TrainingType = "auto" | "manual";

export type TaskStatus = "pending" | "running" | "completed" | "failed";
