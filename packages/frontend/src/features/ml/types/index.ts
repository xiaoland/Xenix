/**
 * ML Types
 *
 * Feature-specific type definitions for ML operations
 */

// ==================== Models ====================

/**
 * ML Model entity
 */
export interface Model {
  id: string;
  name: string;
  type: ModelType;
  family: ModelFamily;
  description?: string;
  hyperparameters: Hyperparameter[];
  defaultParams: Record<string, unknown>;
  isEnabled: boolean;
}

/**
 * Model type
 */
export type ModelType = "regression" | "classification" | "clustering";

/**
 * Model family
 */
export type ModelFamily =
  | "linear"
  | "polynomial"
  | "knn"
  | "tree"
  | "ensemble"
  | "xgboost"
  | "lightgbm"
  | "bayesian";

/**
 * Hyperparameter definition
 */
export interface Hyperparameter {
  name: string;
  type: "number" | "integer" | "string" | "boolean" | "select";
  description?: string;
  defaultValue?: unknown;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  required: boolean;
}

/**
 * Model list response
 */
export interface ModelListResponse {
  models: Model[];
}

// ==================== Tuning ====================

/**
 * Tuning job entity
 */
export interface TuningJob {
  id: string;
  workItemId: string;
  modelId: string;
  datasetId: string;
  targetColumn: string;
  featureColumns: string[];
  params: Record<string, unknown>;
  status: JobStatus;
  metrics?: TuningMetrics;
  bestParams?: Record<string, unknown>;
  startedAt?: string;
  completedAt?: string;
  createdAt: string;
}

/**
 * Job status
 */
export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/**
 * Tuning metrics
 */
export interface TuningMetrics {
  rmse?: number;
  mae?: number;
  r2?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  cvScore?: number;
  cvStd?: number;
}

/**
 * Create tuning job input
 */
export interface CreateTuningJobInput {
  workItemId: string;
  modelId: string;
  datasetId: string;
  targetColumn: string;
  featureColumns: string[];
  params?: Record<string, unknown>;
  cvFolds?: number;
}

// ==================== Prediction ====================

/**
 * Prediction job entity
 */
export interface PredictionJob {
  id: string;
  workItemId: string;
  tuningJobId: string;
  datasetId: string;
  status: JobStatus;
  outputPath?: string;
  result?: PredictionResult;
  startedAt?: string;
  completedAt?: string;
  createdAt: string;
}

/**
 * Prediction result
 */
export interface PredictionResult {
  predictions: number[];
  confidence?: number[];
  featureImportance?: Record<string, number>;
  statistics?: {
    count: number;
    mean: number;
    std: number;
    min: number;
    max: number;
  };
}

/**
 * Create prediction job input
 */
export interface CreatePredictionJobInput {
  workItemId: string;
  tuningJobId: string;
  datasetId: string;
  outputFormat?: "csv" | "json" | "parquet";
}

// ==================== ML Backend ====================

/**
 * ML Backend deployment
 */
export interface MLBackendDeployment {
  id: string;
  name: string;
  type: MLBackendType;
  status: MLBackendStatus;
  endpoint?: string;
  region?: string;
  resources?: MLBackendResources;
  createdAt: string;
  updatedAt: string;
}

/**
 * ML Backend type
 */
export type MLBackendType = "local" | "docker" | "kubernetes" | "aliyun_fc";

/**
 * ML Backend status
 */
export type MLBackendStatus =
  | "pending"
  | "deploying"
  | "running"
  | "error"
  | "stopped";

/**
 * ML Backend resources
 */
export interface MLBackendResources {
  cpu?: string;
  memory?: string;
  gpu?: string;
  instances?: number;
}

// ==================== Column Analysis ====================

/**
 * Column analysis result
 */
export interface ColumnAnalysis {
  name: string;
  type: MLColumnType;
  statistics: ColumnStatistics;
  recommendations: ColumnRecommendation[];
}

/**
 * ML column type for analysis
 */
export type MLColumnType =
  | "numeric"
  | "categorical"
  | "datetime"
  | "text"
  | "boolean";

/**
 * Column statistics
 */
export interface ColumnStatistics {
  count: number;
  nullCount: number;
  uniqueCount: number;
  mean?: number;
  std?: number;
  min?: number;
  max?: number;
  quartiles?: [number, number, number];
  topValues?: { value: string; count: number }[];
}

/**
 * Column recommendation
 */
export interface ColumnRecommendation {
  type: "target" | "feature" | "exclude" | "transform";
  reason: string;
  confidence: number;
}
