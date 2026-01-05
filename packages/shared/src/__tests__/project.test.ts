import { describe, it, expect } from 'vitest';
import type { Project, WorkItem } from '../types/project';

describe('Project Types', () => {
  describe('Project', () => {
    it('should have required fields', () => {
      const project: Project = {
        id: 1,
        name: 'Test Project',
        status: 'active',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      expect(project.id).toBe(1);
      expect(project.name).toBe('Test Project');
      expect(project.status).toBe('active');
      expect(project.createdAt).toBeDefined();
      expect(project.updatedAt).toBeDefined();
    });

    it('should accept optional fields', () => {
      const project: Project = {
        id: 1,
        name: 'Test Project',
        status: 'active',
        description: 'Test description',
        createdBy: 'user-uuid',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        workItems: [],
        datasets: [],
      };

      expect(project.description).toBe('Test description');
      expect(project.createdBy).toBe('user-uuid');
      expect(project.workItems).toEqual([]);
      expect(project.datasets).toEqual([]);
    });

    it('should only accept valid status values', () => {
      const validStatuses: Array<'active' | 'completed' | 'archived'> = [
        'active',
        'completed',
        'archived',
      ];

      validStatuses.forEach((status) => {
        const project: Project = {
          id: 1,
          name: 'Test',
          status,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        expect(project.status).toBe(status);
      });
    });
  });

  describe('WorkItem', () => {
    it('should have required fields', () => {
      const workItem: WorkItem = {
        id: 1,
        projectId: 1,
        name: 'Test WorkItem',
        status: 'active',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      expect(workItem.id).toBe(1);
      expect(workItem.projectId).toBe(1);
      expect(workItem.name).toBe('Test WorkItem');
      expect(workItem.status).toBe('active');
    });

    it('should accept optional ML workflow fields', () => {
      const workItem: WorkItem = {
        id: 1,
        projectId: 1,
        name: 'Test WorkItem',
        status: 'active',
        datasetId: 5,
        featureColumns: ['feature1', 'feature2'],
        targetColumn: 'target',
        selectedModels: ['linear_regression', 'ridge'],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };

      expect(workItem.datasetId).toBe(5);
      expect(workItem.featureColumns).toEqual(['feature1', 'feature2']);
      expect(workItem.targetColumn).toBe('target');
      expect(workItem.selectedModels).toEqual(['linear_regression', 'ridge']);
    });
  });
});
