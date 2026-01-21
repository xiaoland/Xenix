/**
 * Dataset-related type definitions
 */

export interface Dataset {
  id: number;
  projectId?: number;
  name: string;
  description?: string;
  filePath: string;
  fileSize: number;
  columns: string[];
  rowCount: number;
  storage: "local" | "oss"; // Storage type: 'local' (user's device) or 'oss' (cloud storage)
  createdAt: string;
}

export interface ColumnSelection {
  featureColumns: string[];
  targetColumn: string;
  datasetId?: number;
}
