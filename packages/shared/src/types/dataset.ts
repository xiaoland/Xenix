/**
 * Dataset-related type definitions
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

export interface ColumnSelection {
  featureColumns: string[];
  targetColumn: string;
  datasetId?: number;
}
