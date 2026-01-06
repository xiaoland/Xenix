/**
 * Work Item Service
 * Business logic for work item operations
 */
import type { CreateWorkItemDto, UpdateWorkItemDto } from '@xenix/shared';

import { ForbiddenError, NotFoundError } from '../errors/index.js';
import {
  ProjectRepository,
  WorkItemRepository,
} from '../repositories/index.js';

export class WorkItemService {
  private workItemRepo: WorkItemRepository;
  private projectRepo: ProjectRepository;

  constructor() {
    this.workItemRepo = new WorkItemRepository();
    this.projectRepo = new ProjectRepository();
  }

  async getWorkItemsByUser(userId: string, projectId?: number) {
    const userProjects = await this.projectRepo.findByUser(userId);
    const userProjectIds = userProjects.map((p) => p.id);

    if (userProjectIds.length === 0) {
      return [];
    }

    if (projectId) {
      if (!userProjectIds.includes(projectId)) {
        throw new ForbiddenError('Access denied');
      }
      return await this.workItemRepo.findByProject(projectId);
    }

    return await this.workItemRepo.findByProjects(userProjectIds);
  }

  async getWorkItemById(id: number, userId: string) {
    const result = await this.workItemRepo.findByIdWithProject(id);

    if (!result) {
      throw new NotFoundError('Work item');
    }

    if (result.projectCreatedBy !== userId) {
      throw new ForbiddenError('Access denied');
    }

    return result.workItem;
  }

  async createWorkItem(userId: string, data: CreateWorkItemDto) {
    // Verify project exists and belongs to user
    const project = await this.projectRepo.findById(data.projectId);

    if (!project) {
      throw new NotFoundError('Project');
    }

    if (project.createdBy !== userId) {
      throw new ForbiddenError('Access denied');
    }

    return await this.workItemRepo.create({
      projectId: data.projectId,
      name: data.name,
      description: data.description || null,
      status: 'active',
    });
  }

  async updateWorkItem(id: number, userId: string, data: UpdateWorkItemDto) {
    const result = await this.workItemRepo.findByIdWithProject(id);

    if (!result) {
      throw new NotFoundError('Work item');
    }

    if (result.projectCreatedBy !== userId) {
      throw new ForbiddenError('Access denied');
    }

    return await this.workItemRepo.update(id, {
      ...data,
      updatedAt: new Date(),
    });
  }

  async deleteWorkItem(id: number, userId: string) {
    const result = await this.workItemRepo.findByIdWithProject(id);

    if (!result) {
      throw new NotFoundError('Work item');
    }

    if (result.projectCreatedBy !== userId) {
      throw new ForbiddenError('Access denied');
    }

    await this.workItemRepo.delete(id);
  }
}
