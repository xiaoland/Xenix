/**
 * Datasets Types
 * 
 * Feature-specific type definitions for dataset management
 */

/**
 * Dataset entity
 */
export interface Dataset {
  id: string;
  name: string;
  description?: string;
  fileName: string;
  fileSize: number;
  rowCount: number;
  columnCount: number;
  columns?: ColumnInfo[];
  status: DatasetStatus;
  createdAt: string;
  updatedAt: string;
}

/**
 * Dataset status
 */
export type DatasetStatus = "uploading" | "processing" | "ready" | "error";

/**
 * Column information
 */
export interface ColumnInfo {
  name: string;
  type: DatasetColumnType;
  nullable: boolean;
  uniqueCount?: number;
  min?: number;
  max?: number;
  mean?: number;
}

/**
 * Dataset column data type
 */
export type DatasetColumnType = 
  | "string" 
  | "number" 
  | "integer" 
  | "boolean" 
  | "datetime" 
  | "category";

/**
 * Create dataset input
 */
export interface CreateDatasetInput {
  name: string;
  description?: string;
  sourceUrl?: string;
  sourceType?: "url" | "s3" | "gcs";
}

/**
 * Dataset list response
 */
export interface DatasetListResponse {
  datasets: Dataset[];
  total: number;
}

/**
 * Dataset preview (first few rows)
 */
export interface DatasetPreview {
  columns: string[];
  rows: unknown[][];
  totalRows: number;
}

/**
 * Dataset upload progress
 */
export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}
