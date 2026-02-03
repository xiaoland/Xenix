/**
 * Tasks Types
 *
 * Feature-specific type definitions for background task monitoring
 */

/**
 * Task entity
 */
export interface Task {
  id: string;
  workItemId: string;
  type: TaskType;
  status: TaskStatus;
  progress: number;
  message?: string;
  error?: string;
  result?: unknown;
  startedAt?: string;
  completedAt?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Task type
 */
export type TaskType =
  | "dataset_upload"
  | "dataset_process"
  | "tuning"
  | "prediction"
  | "model_training"
  | "model_evaluation";

/**
 * Task status
 */
export type TaskStatus =
  | "pending"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

/**
 * Task log entry
 */
export interface TaskLog {
  id: string;
  taskId: string;
  level: LogLevel;
  message: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

/**
 * Log level
 */
export type LogLevel = "debug" | "info" | "warning" | "error";

/**
 * Task list response
 */
export interface TaskListResponse {
  tasks: Task[];
  total: number;
}

/**
 * Task filter options
 */
export interface TaskFilter {
  status?: TaskStatus;
  type?: TaskType;
  workItemId?: string;
}

/**
 * Task statistics
 */
export interface TaskStats {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
}
