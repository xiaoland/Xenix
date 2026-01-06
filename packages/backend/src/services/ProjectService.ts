/**
 * Project Service
 * Business logic for project operations
 */

import { ProjectRepository } from '../repositories/index.js';
import { NotFoundError, ForbiddenError } from '../errors/index.js';
import type { CreateProjectDto, UpdateProjectDto } from '@xenix/shared';

export class ProjectService {
  private projectRepo: ProjectRepository;

  constructor() {
    this.projectRepo = new ProjectRepository();
  }

  async getAllProjects(userId: string) {
    return await this.projectRepo.findAllWithRelations(userId);
  }

  async getProjectById(id: number, userId: string) {
    const project = await this.projectRepo.findByIdWithRelations(id);

    if (!project) {
      throw new NotFoundError('Project');
    }

    if (project.createdBy !== userId) {
      throw new ForbiddenError('Access denied');
    }

    return project;
  }

  async createProject(userId: string, data: CreateProjectDto) {
    return await this.projectRepo.create({
      name: data.name,
      description: data.description || null,
      status: 'active',
      createdBy: userId,
    });
  }

  async updateProject(id: number, userId: string, data: UpdateProjectDto) {
    const project = await this.projectRepo.findById(id);

    if (!project) {
      throw new NotFoundError('Project');
    }

    if (project.createdBy !== userId) {
      throw new ForbiddenError('Access denied');
    }

    return await this.projectRepo.update(id, {
      ...data,
      updatedAt: new Date(),
    });
  }

  async deleteProject(id: number, userId: string) {
    const project = await this.projectRepo.findById(id);

    if (!project) {
      throw new NotFoundError('Project');
    }

    if (project.createdBy !== userId) {
      throw new ForbiddenError('Access denied');
    }

    await this.projectRepo.delete(id);
  }
}
