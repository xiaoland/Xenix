/**
 * Project and WorkItem-related type definitions
 */

import type { TaskInfo } from "./task";
import type { Dataset } from "./dataset";

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
