/**
 * Project and WorkItem Zod schemas for validation
 */
import { z } from "zod";

export const WorkItemSchema = z.object({
  id: z.number(),
  projectId: z.number(),
  name: z.string(),
  description: z.string().optional(),
  status: z.enum(["active", "completed", "archived"]),
  datasetId: z.number().optional(),
  featureColumns: z.array(z.string()).optional(),
  targetColumn: z.string().optional(),
  selectedModels: z.array(z.string()).optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export const ProjectSchema = z.object({
  id: z.number(),
  createdBy: z.string().uuid().optional(),
  name: z.string(),
  description: z.string().optional(),
  status: z.enum(["active", "completed", "archived"]),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export const CreateProjectSchema = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
});

export const UpdateProjectSchema = z.object({
  name: z.string().min(1).optional(),
  description: z.string().optional(),
  status: z.enum(["active", "completed", "archived"]).optional(),
});

export const CreateWorkItemSchema = z.object({
  projectId: z.number(),
  name: z.string().min(1),
  description: z.string().optional(),
});

export const UpdateWorkItemSchema = z.object({
  name: z.string().min(1).optional(),
  description: z.string().optional(),
  status: z.enum(["active", "completed", "archived"]).optional(),
  datasetId: z.number().optional(),
  featureColumns: z.array(z.string()).optional(),
  targetColumn: z.string().optional(),
  selectedModels: z.array(z.string()).optional(),
});

// Parameter validation schemas
export const ProjectIdParamSchema = z.object({
  id: z.string().regex(/^\d+$/, "Invalid project ID"),
});

export const WorkItemIdParamSchema = z.object({
  id: z.string().regex(/^\d+$/, "Invalid work item ID"),
});

// Type exports
export type WorkItem = z.infer<typeof WorkItemSchema>;
export type Project = z.infer<typeof ProjectSchema>;
export type CreateProjectDto = z.infer<typeof CreateProjectSchema>;
export type UpdateProjectDto = z.infer<typeof UpdateProjectSchema>;
export type CreateWorkItemDto = z.infer<typeof CreateWorkItemSchema>;
export type UpdateWorkItemDto = z.infer<typeof UpdateWorkItemSchema>;
export type ProjectIdParam = z.infer<typeof ProjectIdParamSchema>;
export type WorkItemIdParam = z.infer<typeof WorkItemIdParamSchema>;
