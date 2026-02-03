/**
 * Projects Types
 *
 * Feature-specific type definitions for project management
 */

/**
 * Project entity
 */
export interface Project {
  id: string;
  name: string;
  description?: string;
  status: ProjectStatus;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
  workItemCount?: number;
}

/**
 * Project status
 */
export type ProjectStatus = "active" | "completed" | "archived";

/**
 * Create project input
 */
export interface CreateProjectInput {
  name: string;
  description?: string;
}

/**
 * Update project input
 */
export interface UpdateProjectInput {
  name?: string;
  description?: string;
  status?: ProjectStatus;
}

/**
 * Project list response
 */
export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

/**
 * Project form values
 */
export interface ProjectFormValues {
  name: string;
  description: string;
}
