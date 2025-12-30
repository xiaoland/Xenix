/**
 * Model-related type definitions
 */

export interface ModelOption {
  label: string;
  value: string;
}

export interface TuningMetrics {
  [key: string]: any;
}

export interface TuningResult {
  model: string;
  params?: Record<string, any>;
  metrics?: TuningMetrics;
  status?: string;
  trainingType?: "auto" | "manual";
  createdAt?: string | Date;
}
