import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectService } from '../../services/ProjectService';
import { ForbiddenError, NotFoundError } from '../../errors';
import { ProjectRepository } from '../../repositories/ProjectRepository';

vi.mock('../../repositories/ProjectRepository');

describe('ProjectService', () => {
  let projectService: ProjectService;
  let mockProjectRepo: any;

  beforeEach(() => {
    vi.clearAllMocks();
    projectService = new ProjectService();
    mockProjectRepo = (projectService as any).projectRepo;
  });

  describe('getAllProjects', () => {
    it('should return all projects for a user', async () => {
      const mockProjects = [
        { id: 1, name: 'Project 1', createdBy: 'user-123' },
        { id: 2, name: 'Project 2', createdBy: 'user-123' },
      ];
      mockProjectRepo.findAllWithRelations = vi
        .fn()
        .mockResolvedValue(mockProjects);

      const result = await projectService.getAllProjects('user-123');

      expect(result).toEqual(mockProjects);
      expect(mockProjectRepo.findAllWithRelations).toHaveBeenCalledWith(
        'user-123'
      );
    });
  });

  describe('getProjectById', () => {
    it('should return a project when found and user owns it', async () => {
      const mockProject = {
        id: 1,
        name: 'Test Project',
        createdBy: 'user-123',
      };
      mockProjectRepo.findByIdWithRelations = vi
        .fn()
        .mockResolvedValue(mockProject);

      const result = await projectService.getProjectById(1, 'user-123');

      expect(result).toEqual(mockProject);
    });

    it('should throw NotFoundError when project does not exist', async () => {
      mockProjectRepo.findByIdWithRelations = vi
        .fn()
        .mockResolvedValue(null);

      await expect(
        projectService.getProjectById(999, 'user-123')
      ).rejects.toThrow(NotFoundError);
    });

    it('should throw ForbiddenError when user does not own project', async () => {
      const mockProject = {
        id: 1,
        name: 'Test Project',
        createdBy: 'other-user',
      };
      mockProjectRepo.findByIdWithRelations = vi
        .fn()
        .mockResolvedValue(mockProject);

      await expect(
        projectService.getProjectById(1, 'user-123')
      ).rejects.toThrow(ForbiddenError);
    });
  });

  describe('createProject', () => {
    it('should create a new project', async () => {
      const newProject = {
        name: 'New Project',
        description: 'Test description',
      };
      const createdProject = { id: 1, ...newProject, createdBy: 'user-123' };
      mockProjectRepo.create = vi.fn().mockResolvedValue(createdProject);

      const result = await projectService.createProject('user-123', newProject);

      expect(result).toEqual(createdProject);
      expect(mockProjectRepo.create).toHaveBeenCalledWith({
        name: 'New Project',
        description: 'Test description',
        status: 'active',
        createdBy: 'user-123',
      });
    });
  });

  describe('deleteProject', () => {
    it('should delete a project when user owns it', async () => {
      const mockProject = {
        id: 1,
        name: 'Test Project',
        createdBy: 'user-123',
      };
      mockProjectRepo.findById = vi.fn().mockResolvedValue(mockProject);
      mockProjectRepo.delete = vi.fn().mockResolvedValue(undefined);

      await projectService.deleteProject(1, 'user-123');

      expect(mockProjectRepo.delete).toHaveBeenCalledWith(1);
    });

    it('should throw ForbiddenError when user does not own project', async () => {
      const mockProject = {
        id: 1,
        name: 'Test Project',
        createdBy: 'other-user',
      };
      mockProjectRepo.findById = vi.fn().mockResolvedValue(mockProject);

      await expect(
        projectService.deleteProject(1, 'user-123')
      ).rejects.toThrow(ForbiddenError);
    });
  });
});
