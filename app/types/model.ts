/**
 * Model-related type definitions
 */

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
  trainingType?: "auto" | "manual";
  createdAt?: string | Date;
}
